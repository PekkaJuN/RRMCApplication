# Feature: Receipt reading

## Overview
- **Status:** Done
- **Created:** 2026-10-30
- **Updated:** 2026-10-30: clarifications answered by the user (model
  `qwen3:30b-a3b-instruct-2507-q4_K_M` as the default; empty date and store are stored
  empty; quantity, unit price and time not read; a model timeout fails the image; the fake
  reader chooses its result by image hash; the evaluation tool uses the app's reading code);
  Specify approved by the user; Plan added and approved, with two spec corrections listed
  at its start (PC11, AC24b); Tasks added and approved; implemented (T1–T18), see
  [Changes during implementation](#changes-during-implementation); audited (PASS after one
  fix cycle), see [Audit](#audit); value-range rule for `t` and `a` added to the Validation
  table and AC9 at the user's request (an audit finding: such an answer failed as
  `internal_error`), see [Range rule](#range-rule-after-the-audit)
- **Depends on:** [Receipt import](receipt-import.md), [Model evaluation](model-evaluation.md)
- **Implements:** PRD FR-6, FR-7, FR-8, FR-9, FR-10 (storing the OCR text), FR-31 (model
  check before and during an import run); NFR-1, NFR-3, NFR-7, NFR-8 and NFR-13 for reading;
  PRD open question 4 (model choice).
- **Affected subsystems:** [receipt-reading](../../docs/subsystems/receipt-reading/README.md),
  [import](../../docs/subsystems/import/README.md),
  [storage](../../docs/subsystems/storage/README.md), [ui](../../docs/subsystems/ui/README.md)

## Problem Statement
An import run records each new image as a receipt, but it does not read it: the receipt has
no store, date, total or lines, so nothing can be categorized, reviewed or totalled (PRD
section 5, step 3). This spec adds the reading step to the run: turn the image upright,
preprocess it, read the text with Tesseract, and turn the text into a validated structured
receipt with the local model. The model evaluation (2026-10-29, 25 real receipts) chose the
OCR path with `qwen3:30b-a3b-instruct-2507-q4_K_M`: median 18 s per receipt, but only 60 % of
totals and dates right, so the result must be easy to correct later and the reading step
must stay swappable for a vision model.

## Current Behavior
- An import run lists the import folder, checks the format, computes the image identifier,
  skips duplicates, stores a receipt row (identifier, file name, import time) and moves the
  file ([import](../../docs/subsystems/import/README.md), @backend/app/receipt_import/run.py).
  It does not open the image.
- `OcrEngine` and `ReceiptModel` exist with `check()` and `load()` only, plus fakes chosen by
  `RRMC_ENGINES` ([receipt-reading](../../docs/subsystems/receipt-reading/README.md)).
- The evaluation tool (@backend/evaluation/) has the preprocessing, orientation, prompt and
  answer schema that this spec takes into the app. It is a development tool; the app does
  not import it.
- The `receipts` table has no read data and there is no `receipt_lines` table
  ([datamodel.md](../../docs/datamodel.md#receipts)).
- The model check before a run (FR-31) is not done; `RRMC_MODEL` defaults to `qwen2.5:7b`.

## Proposed Change

### Concepts

- **Reading** turns one image into a **read receipt**: store name, purchase date, total in
  integer cents, lines, and the raw OCR text.
- A **receipt reader** is the one interface for reading: image bytes in, read receipt out.
  This spec has one implementation, the **OCR reader** (Tesseract, then the text model).
  A vision reader can be added later behind the same interface (needs a new ADR, because
  [ADR 0001](../../docs/adr/0001-tech-stack.md) names Tesseract).
- A **read line** has a name as printed, an amount in integer cents (after any merged
  discount and deposit, PRD FR-9), and a deposit refund flag.

### Parts

- **PC1 Orientation and preprocessing (FR-6).** The same steps as the evaluation tool's
  `ocr:` variants ([model evaluation](model-evaluation.md) PC4), in this order: turn upright
  from the EXIF orientation tag (1–8; a missing, unreadable or out-of-range tag leaves the
  image as it is); grayscale; upscale to at least 1 500 px wide; automatic contrast;
  orientation detection (Tesseract OSD) that turns the image by 90, 180 or 270 degrees when
  its confidence is at least 2.0, and leaves it as it is otherwise, without error.
- **PC2 OCR (FR-7).** Tesseract reads the preprocessed image with `-l fin+eng --psm 4`.
  The whole OCR text is kept as Tesseract returns it.
- **PC3 Parsing (FR-8, FR-9).** The OCR text goes to the model named by `RRMC_MODEL` with
  the evaluation tool's prompt (Finnish receipt rules of FR-9) and answer schema
  `{"s", "d", "t", "l": [{"n", "a", "r"}]}`, through Ollama's structured output with
  temperature 0. The answer is validated (see [Validation](#validation)); an invalid answer
  fails the image, it is never stored as partial data.
- **PC4 One reader interface.** Import calls only the receipt reader. A deterministic fake
  reader is used when `RRMC_ENGINES=fake` (NFR-13).
- **PC5 Storing (FR-10).** The read data is stored in the same transaction as the receipt
  row: on the receipt the store name, purchase date, total and OCR text; one line row per
  read line in printed order with its position, name, amount and deposit refund flag.
  Lines get no category in this spec (categorization adds it). Receipts imported before this
  feature keep empty read fields.
- **PC6 Import run with reading.** Reading runs for each new image after the duplicate check
  and before the commit. A reading failure fails the image like other failures: nothing is
  stored, the file moves to the failed folder, and its identifier is not stored (FR-4).
- **PC7 Model check (FR-31).** A run starts only when OCR and the model are available
  (`check()` returns `ok`). If Ollama or the model becomes unavailable during a run, the run
  stops: the current image and all images after it stay in the import folder, nothing is
  stored for them, and the report says the run stopped and why. No image moves to the failed
  folder because the model was unavailable.
- **PC8 Privacy (NFR-1, NFR-3).** OCR text and prompts go only to `RRMC_OLLAMA_URL`; the
  client ignores proxy variables (`trust_env=False`, [learnings](../../docs/learnings.md)).
  A model name ending in `-cloud` or `:cloud` is refused at start, as in the evaluation tool.
  Logs and error messages carry no OCR text, model answer, store or product name.
- **PC9 Tuonti page.** The page shows the new failure reasons, the refusal when the model or
  OCR is unavailable, and a stopped run.
- **PC10 Default model.** `.env.example` sets `RRMC_MODEL` to
  `qwen3:30b-a3b-instruct-2507-q4_K_M`, the exact tag that was evaluated (the plain tag
  `qwen3:30b-a3b` may point to another build). PRD FR-29 is updated to name it as the
  default; switching model still only needs the setting changed. ADR 0003 records the
  choice with the aggregate evaluation numbers only.
- **PC11 Evaluation tool uses the app's reading code.** The evaluation tool's `ocr:` variants
  use the app's preprocessing, orientation, prompt, answer schema and schema parsing instead
  of their own copies (not the app's extra validation rules, which would change the tool's
  `valid` metric), so what is evaluated is what the app ships. Its behavior and existing
  tests stay the same; only where the code lives changes.

### Validation

An answer is valid when all of these hold; otherwise the image fails with `parse_failed`.

| Field | Rule |
|---|---|
| whole answer | JSON that matches the schema exactly (strict types: `t` and `a` integers, `r` boolean) |
| `s` | Store name; surrounding spaces are trimmed. An empty name is valid and stored as `""`; the user fixes it in review |
| `d` | A real calendar date as `YYYY-MM-DD` is stored. Anything else (empty, another format, an impossible date such as `2026-02-30`) is valid and stored as no date (`NULL`); the user fixes it in review. The evaluation got the date right on 60 % of receipts, so failing these images would fail many receipts |
| `t` | Integer cents, ≥ 0 and ≤ 2^63 − 1 (the SQLite integer limit) |
| `l` | At least one line; each `n` not empty after trimming; `a` an integer from −2^63 to 2^63 − 1; `r` true only with `a` < 0 |

A total that differs from the sum of the lines is **not** a reading failure; the review UI
warns about it (FR-20).

Quantity, unit price and purchase time (FR-8) are not read and no columns are added for
them: the evaluation's answer schema has none of them, and each extra field costs output
time on the CPU. PRD FR-8 gets a note; the review UI spec decides whether the user can
enter them.

### Failure reasons (added to the import spec's table)

| `reason` | `message` | When |
|---|---|---|
| `unreadable_image` | `Kuvaa ei voitu avata.` | The file has a valid signature but cannot be decoded as an image |
| `ocr_failed` | `Tekstin tunnistus epäonnistui.` | Tesseract exits with an error or exceeds its time limit |
| `no_text` | `Kuvasta ei löytynyt tekstiä.` | The OCR text is empty or only whitespace |
| `parse_failed` | `Kuittia ei voitu tulkita.` | The model's answer is not valid (see [Validation](#validation)), or no answer arrives within 300 s |

The model time limit is 300 s, one constant in the code: above the NFR-8 target of 180 s, so
a slow but correct answer is not lost. A timeout fails only that image. A connection that
cannot be made, or an Ollama error saying the model is missing, stops the run (PC7).

### Run state changes (`GET /api/import`)

New field `stopped`: `null` when the run went through all files, or
`{"reason": "model_unavailable", "message": "Kielimalli ei vastaa. Tuonti pysäytettiin; jäljellä olevat kuvat jäivät tuontikansioon."}`
when PC7 stopped it. `processed` then is less than `total`.

### API errors (added)

| Method and path | Status | `error` | `message` | When |
|---|---|---|---|---|
| `POST /api/import` | 503 | `model_unavailable` | `Kielimalli ei ole käytettävissä. Käynnistä Ollama ja tarkista mallin nimi.` | `ReceiptModel.check()` is not `ok` |
| `POST /api/import` | 503 | `ocr_unavailable` | `Tekstintunnistus ei ole käytettävissä.` | `OcrEngine.check()` is not `ok` |

The folder check (`folders_unavailable`) runs first, then OCR, then the model.

### UI texts (Tuonti page, added)

| Use | Text |
|---|---|
| Stopped run | the `stopped.message` |
| Refused start | the API error `message` |
| Failure items | the `message` of the reason |

### Out of Scope
- Categorization of lines (FR-11–FR-15): the categorization spec adds categories and the
  category source to the lines.
- The review UI, the receipts list and the line-sum warning (FR-16–FR-21).
- Re-parsing a stored OCR text with a different model or prompt (PRD "Later (candidates)").
  This spec only stores the text so it can be done later.
- A vision reader and a setting to choose it.
- Quantity, unit price and purchase time (see [Validation](#validation)).
- Reading the receipts imported before this feature.
- Content-based duplicate detection, e-receipts, HEIC and PDF.
- Retrying a failed read automatically.

## Acceptance Criteria

Unless an AC says otherwise: the folders exist and can be written to, OCR and the model are
available, the database has no receipts, and "the run finishes" means `GET /api/import`
returns state `finished`. Images are synthetic. "The reader returns R" means a test double
of the OCR engine or the model returns the stated value.

### Preprocessing

#### AC1: EXIF orientation turns the image upright
**Given** a synthetic 400 × 300 JPEG whose EXIF orientation tag is 6
**When** it is preprocessed
**Then** the image given to OSD is grayscale, 1 500 × 2 000 px (upright 300 × 400, scaled to
1 500 px wide), and its content is the upright receipt

#### AC2: Image without or with a broken EXIF tag is left as it is
**Given** synthetic upright JPEGs with no EXIF, with orientation 1, and with orientation 9
**When** each is preprocessed
**Then** none is rotated; each is grayscale and at least 1 500 px wide

#### AC3: OSD turns a sideways image when it is sure enough
**Given** a preprocessed image and OSD reporting `Rotate: 90` with confidence 2.0
**When** orientation detection runs
**Then** the image given to OCR is the image rotated 90° clockwise

#### AC4: OSD that is unsure or fails changes nothing
**Given** OSD reports `Rotate: 90` with confidence 1.9; or `Rotate: 0`; or exits with an
error; or its output lacks the fields
**When** orientation detection runs
**Then** the image given to OCR is unchanged and reading continues without error

#### AC5: Wide image is not downscaled
**Given** an upright image 2 400 px wide
**When** it is preprocessed
**Then** it stays 2 400 px wide

### Reading and validation

#### AC6: A valid answer becomes a read receipt
**Given** OCR returns the text `T` and the model answers
`{"s": " K-Market Testi ", "d": "2026-10-05", "t": 349, "l": [{"n": "Maito 1l", "a": 125, "r": false}, {"n": "Limu 1,5l", "a": 264, "r": false}, {"n": "Panttipalautus", "a": -40, "r": true}]}`
**When** the image is read
**Then** the read receipt has store `"K-Market Testi"`, date 2026-10-05, total 349, OCR text
`T`, and three lines in that order with amounts 125, 264 and −40, only the third marked as
a deposit refund

#### AC7: The model gets the OCR text and the chosen settings
**Given** `RRMC_MODEL=m` and OCR returns `T`
**When** the image is read
**Then** exactly one request goes to `<RRMC_OLLAMA_URL>/api/generate` with model `m`, a
prompt that contains `T` and the FR-9 rules, `format` set to the answer schema, temperature
0 and `stream` false

#### AC8: Answer that is not JSON or does not match the schema
**Given** the model answers `not json`; or `{"s": "x", "d": "2026-10-05", "t": 3.49, "l": []}`;
or an answer without `l`; or `"a": "125"`
**When** the image is read
**Then** reading fails with `parse_failed`

#### AC9: Answer that breaks a validation rule
**Given** a schema-valid answer with `"l": []`; or a line with `"n": "  "`; or `"t": -1`; or
a line with `"r": true` and `"a": 40`; or `"t": 9223372036854775808` (2^63); or a line with
`"a": -9223372036854775809` (−2^63 − 1)
**When** the image is read
**Then** reading fails with `parse_failed`

#### AC10: Date that is not a real date is stored empty
**Given** a schema-valid answer, otherwise as AC6, with `"d"` set to `"2026-02-30"`,
`"05.10.2026"` or `""`
**When** the image is read
**Then** reading succeeds and the read receipt has no date (`None`); store, total and lines
are as in AC6

#### AC10b: Empty store name is stored empty
**Given** a schema-valid answer, otherwise as AC6, with `"s": "  "`
**When** the image is read
**Then** reading succeeds and the store name is `""`

#### AC11: Unreadable image
**Given** a file `bad.jpg` that starts with `FF D8 FF` but is not a decodable image
**When** the run finishes
**Then** `failures` is `[{"file_name": "bad.jpg", "reason": "unreadable_image", "message": "Kuvaa ei voitu avata."}]`,
the file is in the failed folder and no receipt exists

#### AC11b: Model answer times out
**Given** the import folder holds `a.jpg` and `b.jpg`; the model gives no answer for `a.jpg`
within 300 s and a valid answer for `b.jpg`
**When** the run finishes
**Then** `a.jpg` fails with `parse_failed` and is in the failed folder; `b.jpg` is imported;
`stopped` is `null`

#### AC12: OCR fails or finds no text
**Given** Tesseract exits with code 1 for `a.jpg`; and OCR returns `" \n "` for `b.jpg`
**When** the run finishes
**Then** `a.jpg` fails with `ocr_failed`, `b.jpg` with `no_text`, both are in the failed
folder, no receipt exists, and the model was not called

### Import run

#### AC13: An imported receipt has its read data and lines
**Given** the import folder holds `a.jpg` and the reader returns the receipt of AC6
**When** the run finishes
**Then** `imported` is 1; the receipt row has the AC6 store, date `"2026-10-05"`,
`total_cents` 349 and `ocr_text` `T`; three line rows reference it with positions 1, 2, 3,
the AC6 names and amounts, deposit refund flags false, false, true, and no category; and
`a.jpg` is in the done folder

#### AC14: A reading failure stores nothing and the run goes on
**Given** the import folder holds `a.jpg` (model answers `not json`) and `b.jpg` (valid answer)
**When** the run finishes
**Then** `imported` is 1, `failures` is `[{"file_name": "a.jpg", "reason": "parse_failed", "message": "Kuittia ei voitu tulkita."}]`;
`a.jpg` is in the failed folder; one receipt exists, for `b.jpg`, with its lines; no line
row references any other receipt

#### AC15: Duplicates are not read
**Given** a receipt with `image_hash` `H` exists and the import folder holds `again.jpg` with SHA-256 `H`
**When** the run finishes
**Then** `duplicates` is `["again.jpg"]` and neither OCR nor the model was called

#### AC16: Failed save rolls back the receipt and its lines
**Given** the reader returns the AC6 receipt and writing the second line row fails
**When** the run finishes
**Then** `a.jpg` fails with `save_failed`, no receipt row and no line row exist, and the file
is in the failed folder

#### AC17: Failed move removes the receipt and its lines
**Given** the reader returns the AC6 receipt and moving `a.jpg` to the done folder fails
**When** the run finishes
**Then** `a.jpg` fails with `move_failed`, no receipt row and no line row exist, and `a.jpg`
is still in the import folder

### Model and OCR availability

#### AC18: Start refused when the model is unavailable
**Given** `ReceiptModel.check()` returns `unavailable` (or `missing_model`) and the import
folder holds `a.jpg`
**When** the user starts an import
**Then** `POST /api/import` returns 503 with `error` `model_unavailable` and the AC message;
`a.jpg` is still in the import folder; the run state is unchanged

#### AC19: Start refused when OCR is unavailable
**Given** `OcrEngine.check()` returns `unavailable`
**When** the user starts an import
**Then** `POST /api/import` returns 503 with `error` `ocr_unavailable`; nothing is processed

#### AC20: Model lost during a run stops the run
**Given** the import folder holds `a.jpg`, `b.jpg`, `c.jpg`; `a.jpg` is read; the model call
for `b.jpg` cannot connect to Ollama
**When** the run finishes
**Then** `total` 3, `processed` 1, `imported` 1, `failures` [], `stopped` has reason
`model_unavailable` and the AC message; `a.jpg` is in the done folder; `b.jpg` and `c.jpg`
are still in the import folder; only `a.jpg`'s receipt exists

#### AC21: Cloud model refused
**Given** `RRMC_MODEL=qwen3:cloud` (or a name ending in `-cloud`)
**When** the user starts an import
**Then** `POST /api/import` returns 503 with `error` `model_unavailable` and no request goes
to Ollama for reading

### Privacy

#### AC22: Nothing of the receipt in the log
**Given** a run with one imported, one `parse_failed` and one `ocr_failed` image, whose OCR
text, model answer, store and line names contain the marker `SECRET-7f3a`, and file names
contain `NAME-91c2`
**When** the run finishes
**Then** the captured log contains neither marker

#### AC23: Proxy settings are ignored
**Given** `HTTP_PROXY` and `ALL_PROXY` point to another address
**When** an image is read
**Then** the model request goes to `RRMC_OLLAMA_URL` and no request goes to the proxy

### Fakes

#### AC24: Fake reader returns a fixed receipt
**Given** `RRMC_ENGINES=fake` and the import folder holds two different valid images
**When** the run finishes, and again after the files are moved back and the database is reset
**Then** every receipt of both runs has store `"Testikauppa"`, date `"2026-10-05"`,
`total_cents` 349, OCR text `"TESTIKAUPPA\nMAITO 1,25\nLIMU 2,24\nYHTEENSÄ 3,49"` and two
lines (`"Maito"` 125, `"Limu"` 224, not deposit refunds); neither Tesseract nor Ollama is
called

#### AC24b: Fake reader fails images chosen by hash
**Given** `RRMC_ENGINES=fake` and the import folder holds `parse-failed.png` with the bytes
of the constant `FAKE_PARSE_FAILED_IMAGE`, whose SHA-256 is listed in the fake reader's
table with result `parse_failed`
**When** the run finishes
**Then** the file fails with `parse_failed` and is in the failed folder; no receipt exists

### Tuonti page

#### AC25: Refused start is shown
**Given** `POST /api/import` returns 503 `model_unavailable`
**When** the user presses "Tuo kuitit"
**Then** the page shows `Kielimalli ei ole käytettävissä. Käynnistä Ollama ja tarkista mallin nimi.`
and the button is enabled again

#### AC26: Stopped run is shown
**Given** `GET /api/import` returns a finished run with `stopped` set as in AC20
**When** the Tuonti page shows the report
**Then** it shows the counts and the `stopped.message`

#### AC27: New failure reasons are shown
**Given** a finished run with one failure of each new reason
**When** the Tuonti page shows the report
**Then** each failure shows its file name and the message from the failure reason table

## Files to Modify
Refined in the Plan phase.

| File | Change |
|---|---|
| `backend/app/engines/ocr.py` | `orient()`, `read()`, `Oriented`, `OcrError`; `run_image` runner; fake |
| `backend/app/engines/model.py` | `generate()`, `is_cloud_model()`, three errors; `trust_env=False`; fake |
| `backend/app/receipt_reading/__init__.py`, `preprocess.py`, `prompt.py`, `receipt.py`, `validation.py`, `reader.py`, `fake.py`, `factory.py` (new) | See [Plan](#components) |
| `backend/app/receipt_import/run.py`, `service.py`, `schemas.py`, `errors.py` | Reading step, new reasons, start checks, `stopped` |
| `backend/app/main.py` | Pass engines and reader to `ImportService` |
| `backend/app/health/service.py` | `ModelLoader` takes `LoadableModel` (`check`, `load`), the part of `ReceiptModel` it uses |
| `backend/app/storage/migrations/0003_receipt_reading.sql` (new) | Read fields on `receipts`; `receipt_lines` |
| `backend/app/storage/receipt_repository.py` | Read fields in `add`, `add_line`, `lines` |
| `backend/app/texts.py` | Finnish messages |
| `backend/app/settings.py` | `model` default (PC10) |
| `backend/evaluation/ocr.py`, `prompt.py` | Wrappers over the app code (PC11); evaluation tests unchanged |
| `backend/tests/unit/test_settings.py`, `backend/tests/integration/test_health.py` | Default model per foundation AC6 as corrected by this spec (the health test uses the default settings) |
| `backend/tests/unit/storage/test_receipts_schema.py`, `backend/tests/receipt_import_data.py` | The receipts table test allows the columns of later migrations (as the catalog test does); the failing-repository double passes the read fields on |
| `backend/tests/integration/test_import_api.py` | The idle state has `stopped: null` |
| `backend/tests/unit/receipt_import/test_import_run.py` | `process_file` now needs a reader (the fake); the AC1 check compares the image record fields, as receipt-import AC1 states, not the read fields |
| `backend/tests/` (new tests) | Unit and integration tests below |
| `frontend/src/api/imports.ts`, `frontend/src/components/ImportPage.tsx`, `frontend/src/test/imports.ts` | `stopped`, new reasons; component tests |
| `frontend/e2e/import.spec.ts` | Parse failure journey |
| `.env.example` | `RRMC_MODEL` default (PC10) |
| `specs/features/foundation.md` | PC3 default and AC6 name the new default model, with a note pointing here |
| `docs/adr/0003-receipt-reading-model.md` (new, written with the Plan) | Model choice, OCR path, aggregate evaluation numbers |
| `docs/development.md`, `AGENTS.md` | `ollama pull` of the new default model |
| `docs/subsystems/receipt-reading/README.md` | Full subsystem description |
| `docs/subsystems/import/README.md`, `docs/subsystems/ui/README.md` | Reading step, checks, `stopped` |
| `docs/datamodel.md`, `docs/api-reference.md`, `docs/architecture.md`, `docs/glossary.md`, `docs/content-plan.md` | New fields and table, API changes, resolved open question 4, terms (read receipt, receipt reader) |
| `specs/PRD.md` | Open question 4 resolved; FR-8 and FR-29 notes per the clarifications |
| `specs/README.md` | Row for this spec |

## Risk
- **What could break:** the import run (every image now goes through OCR and the model, so a
  run takes minutes instead of seconds; a reading bug could fail every image and fill the
  failed folder); the migration on the user's existing database (receipts already imported
  must stay); the model may not fit or be too slow (60 % totals and dates means many
  receipts need correction until the review UI exists).
- **Rollback:** failed images can be moved back to the import folder and retried (FR-4).
  The migration only adds nullable columns and a new table; the previous code ignores them.
  The model is one setting.
- **Dependencies:** Tesseract 5 with `fin` and `eng` in the backend container; Ollama on
  Windows with the chosen model pulled; Pillow (already a dependency of the evaluation tool).

## Testing Strategy (MANDATORY)

### Unit tests
| AC | Function | Case | Given | When | Then | Mocks |
|---|---|---|---|---|---|---|
| AC1 | `preprocess` | EXIF 6 | 400 × 300 JPEG, tag 6 | preprocess | grayscale 1 500 × 2 000, upright | none |
| AC2 | `preprocess` | no / 1 / 9 tag | upright JPEGs | preprocess | not rotated | none |
| AC5 | `preprocess` | wide | 2 400 px wide | preprocess | 2 400 px wide | none |
| AC3 | `TesseractOcrEngine.orient` | sure | OSD 90, conf 2.0 | orient | rotated 90° clockwise | command runner |
| AC4 | `TesseractOcrEngine.orient` | unsure / fails | conf 1.9, rotate 0, exit 1, bad output | orient | unchanged, no error | command runner |
| AC12 | `TesseractOcrEngine.read` | error | exit 1; timeout | read | `ocr_failed` | command runner |
| AC12 | OCR reader | no text | OCR `" \n "` | read | `no_text`, model not called | OCR, model |
| AC6 | answer validation | valid | AC6 answer | validate | AC6 read receipt | none |
| AC8 | answer validation | schema errors | four answers | validate | `parse_failed` | none |
| AC9 | answer validation | rule errors | six answers, two at the integer limits | validate | `parse_failed` | none |
| AC10 | answer validation | dates | three dates | validate | date `None`, rest as AC6 | none |
| AC10b | answer validation | empty store | `"s": "  "` | validate | store `""` | none |
| AC11b | `OllamaReceiptModel` parse call | timeout | transport raises read timeout | parse | `parse_failed` | `httpx2.MockTransport` |
| AC7 | `OllamaReceiptModel` parse call | request | model `m`, text `T` | parse | one request with the AC7 body | `httpx2.MockTransport` |
| AC20 | `OllamaReceiptModel` parse call | connection lost | transport raises connect error | parse | model-unavailable error | `httpx2.MockTransport` |
| AC23 | `OllamaReceiptModel` | proxy | proxy env set | parse | request to `RRMC_OLLAMA_URL` only | `httpx2.MockTransport`, env |
| AC21 | model name check | cloud | `x:cloud`, `x-cloud` | check | refused | none |
| AC24 | fake reader | fixed receipt | two images | read twice | AC24 receipt both times | none |
| AC24b | fake reader | listed hash | `parse-failed.png` bytes | read | `parse_failed` | none |
| PC11 | evaluation tool | unchanged behavior | existing evaluation tests | run | all green, unchanged | as today |

### Integration tests
Real SQLite (temporary file) and real FastAPI app; OCR and model replaced by test doubles
unless the row says otherwise.
| AC | Scenario | Request / input | Expected output | Status |
|---|---|---|---|---|
| AC13 | imported with lines | `POST /api/import`, poll `GET` | receipt row and three lines as AC13 | 202, 200 |
| AC14 | one failure, run goes on | two images | AC14 state, rows | 202, 200 |
| AC15 | duplicate not read | existing hash | no reader call | 202, 200 |
| AC11 | unreadable image | `bad.jpg` | `unreadable_image` | 202, 200 |
| AC12 | OCR failure and no text | two images | `ocr_failed`, `no_text` | 202, 200 |
| AC11b | model timeout | two images | `a.jpg` `parse_failed`, `b.jpg` imported, `stopped` null | 202, 200 |
| AC10 | date stored empty | answer with `"d": ""` | receipt row `purchase_date` `NULL` | 202, 200 |
| AC16 | save fails on a line | repository fails on line 2 | `save_failed`, no rows | 202, 200 |
| AC17 | move fails | file store fails on move | `move_failed`, no rows | 202, 200 |
| AC18 | model unavailable at start | `POST /api/import` | `model_unavailable` | 503 |
| AC19 | OCR unavailable at start | `POST /api/import` | `ocr_unavailable` | 503 |
| AC20 | model lost mid-run | three images | AC20 state, files | 202, 200 |
| AC21 | cloud model | `POST /api/import` | `model_unavailable`, no reading request | 503 |
| AC22 | log | three images with markers | no marker in `caplog` | 202, 200 |
| AC24 | fakes | `RRMC_ENGINES=fake`, two runs | AC24 data in both runs | 202, 200 |
| AC24b | fake failure | `parse-failed.png` | `parse_failed` | 202, 200 |
| AC1, AC3 | real Tesseract | synthetic receipt rendered sideways with EXIF 6, and one rotated without EXIF | OCR text contains the rendered words | n/a |

### E2E tests
| AC | Journey | Steps | Expected outcome |
|---|---|---|---|
| AC13, AC24 | Import reads a receipt | Copy a synthetic JPEG into the import folder; press "Tuo kuitit"; wait for the report | `Tuotu: 1`; the database row has the fake reader's data |
| AC24b, AC27 | Unreadable receipt is reported | Write `FAKE_PARSE_FAILED_IMAGE` bytes as `parse-failed-<run>.png` into the import folder; press "Tuo kuitit"; wait for the report | `Epäonnistui: 1`; the failure shows that file name and `Kuittia ei voitu tulkita.` |
| AC25 | Refused start | Not possible with the fakes (always `ok`); covered by a component test with MSW | n/a |

Component tests (Vitest + MSW): AC25, AC26, AC27.

### Coverage target
- Backend: 90 % lines for `receipt_reading` and the changed import code; every branch of
  validation, orientation and the run's failure handling tested.
- Frontend: every new state of the Tuonti page has a component test.

### Test data
- Synthetic fixtures only: receipt images rendered with Pillow from invented text (stores
  like "K-Market Testi", products like "Maito 1l"), saved with and without EXIF orientation
  tags; OCR texts and model answers written by hand; the byte constant
  `FAKE_PARSE_FAILED_IMAGE` for the fake reader's table.
- Mocks: command runner for Tesseract, `httpx2.MockTransport` for Ollama, `FileStore` and
  repository doubles for failures.

## Related Documentation (MANDATORY)
- Tier 1: [architecture.md](../../docs/architecture.md#import-fr-45-started-with-a-button),
  [datamodel.md](../../docs/datamodel.md#receipts),
  [api-reference.md](../../docs/api-reference.md), [learnings.md](../../docs/learnings.md)
  (2026-10-29 orientation; 2026-10-28 proxy and file name leaks), [PRD](../PRD.md) FR-6–FR-10,
  FR-29, FR-31, open question 4
- Tier 2: [receipt-reading](../../docs/subsystems/receipt-reading/README.md),
  [import](../../docs/subsystems/import/README.md),
  [storage](../../docs/subsystems/storage/README.md), [ui](../../docs/subsystems/ui/README.md)
- Specs: [receipt import](receipt-import.md), [model evaluation](model-evaluation.md)
- ADRs: [0001 technology stack](../../docs/adr/0001-tech-stack.md), [0003 receipt-reading model](../../docs/adr/0003-receipt-reading-model.md)

<!-- The Plan phase appends "## Plan" and the Tasks phase appends "## Tasks" below. -->

## Plan

### Changes to the spec found while planning

Approved with the Plan, both keep the behavior the user agreed to:

1. **PC11:** the evaluation tool takes the app's answer *schema parsing* (`parse_answer`),
   not the app's extra validation rules (at least one line, total ≥ 0, ...). Otherwise the
   tool's `valid` metric and its existing tests would change, which PC11 rules out. The
   rules are applied by the app on top of the parsed answer.
2. **AC24b:** the "committed fixture" is a byte constant, `FAKE_PARSE_FAILED_IMAGE`
   (the PNG signature followed by `rrmc fake reader: parse_failed`), defined next to the
   fake reader. Backend tests use it directly; the E2E test writes the same bytes. The
   fake reader never decodes an image, so it needs no real PNG, and the existing import E2E
   test (JPEG-signed bytes that are not an image) keeps passing.

### Components

```
backend/app/
  engines/
    ocr.py          OcrEngine: check(), orient(image), read(image); Tesseract and fake
    model.py        ReceiptModel: check(), load(), generate(prompt, schema); Ollama and fake;
                    is_cloud_model(); ModelUnavailableError, ModelTimeoutError, ModelAnswerError
    factory.py      unchanged shape: Engines(ocr, model)
  receipt_reading/  (new package)
    preprocess.py   exif_orientation(), preprocess() (moved from evaluation/ocr.py);
                    UnreadableImageError
    prompt.py       ANSWER_SCHEMA, INSTRUCTIONS, Answer, AnswerLine, text_prompt(),
                    parse_answer() (moved from evaluation/prompt.py)
    receipt.py      ReadReceipt, ReadLine (frozen dataclasses); ReadFailedError(reason)
    validation.py   to_read_receipt(answer, ocr_text) -> ReadReceipt
    reader.py       ReceiptReader protocol; OcrReceiptReader(ocr, model)
    fake.py         FakeReceiptReader, FAKE_RECEIPT, FAKE_PARSE_FAILED_IMAGE
    factory.py      create_reader(settings, engines) -> ReceiptReader
  receipt_import/   reading step, start checks, `stopped`
  storage/          migration 0003, repository: read fields and lines
backend/evaluation/ ocr.py and prompt.py become thin wrappers over the app code (PC11)
```

Dependencies keep the [architecture rules](../../docs/architecture.md#dependency-rules):
`receipt_import` → `receipt_reading` → `engines`; `receipt_import` → `storage`. Storage takes
plain values (no `ReadReceipt`), so it does not depend on `receipt_reading`. `engines` does
not import `receipt_reading`; the reader is built in `receipt_reading/factory.py` from the
engines `create_engines` already returns. The evaluation tool imports from `app`; the app
never imports `evaluation`.

### Data flow of one new image

```mermaid
sequenceDiagram
  participant I as import (process_file)
  participant R as OcrReceiptReader
  participant O as OcrEngine
  participant M as ReceiptModel
  participant S as storage
  I->>I: format check, SHA-256, duplicate check
  I->>R: read(image bytes)
  R->>R: preprocess (EXIF, grayscale, scale, contrast)
  R->>O: orient(png) then read(png)
  O-->>R: OCR text
  R->>M: generate(text_prompt(text), ANSWER_SCHEMA)
  M-->>R: raw JSON
  R->>R: parse_answer, to_read_receipt
  R-->>I: ReadReceipt (or ReadFailedError / ModelUnavailableError)
  I->>S: one transaction: add receipt with read fields, add_line × n
  I->>I: move file to done folder (delete receipt on failure; lines cascade)
```

### Reader

`ReceiptReader.read(image: bytes) -> ReadReceipt` raises `ReadFailedError(reason)` with
`reason` one of `unreadable_image`, `ocr_failed`, `no_text`, `parse_failed`, or lets
`ModelUnavailableError` through.

`OcrReceiptReader.read`:

1. `preprocess(image)`; a Pillow error (`UnidentifiedImageError`, `OSError`,
   `DecompressionBombError`, `SyntaxError` from a broken file) → `unreadable_image`.
2. `ocr.orient(png)` (never raises) then `ocr.read(oriented)`; `OcrError` → `ocr_failed`.
3. Text empty after `strip()` → `no_text`; the model is not called.
4. `model.generate(text_prompt(text), ANSWER_SCHEMA)`; `ModelTimeoutError` and
   `ModelAnswerError` → `parse_failed`; `ModelUnavailableError` propagates.
5. `parse_answer(raw)` is `None` → `parse_failed`; `to_read_receipt(answer, text)`.

`ocr_text` is stored as Tesseract returned it (not stripped).

`to_read_receipt` applies the [validation table](#validation): trim `s`; `d` through
`date.fromisoformat` only when it matches `^\d{4}-\d{2}-\d{2}$` (otherwise, or on
`ValueError`, `None`); `t` < 0, no lines, an empty name after trimming, or `r` with `a` ≥ 0
→ `parse_failed`. Line names are trimmed.

```python
@dataclass(frozen=True)
class ReadLine:
    name: str
    amount_cents: int
    is_deposit_refund: bool

@dataclass(frozen=True)
class ReadReceipt:
    store: str
    purchase_date: date | None
    total_cents: int
    lines: tuple[ReadLine, ...]
    ocr_text: str
```

`FakeReceiptReader.read` returns `FAKE_RECEIPT` (the AC24 values) for every image, except
an image whose SHA-256 is in its table `{sha256(FAKE_PARSE_FAILED_IMAGE): "parse_failed"}`,
which raises `ReadFailedError("parse_failed")`. It does not call the engines.

### Engines

**`OcrEngine`** gains the evaluation tool's two methods, with the same behavior
(model evaluation PC4):

| Method | Tesseract | Fake |
|---|---|---|
| `orient(image: bytes) -> Oriented` | `tesseract stdin stdout --psm 0`; turns by `Rotate` when 90/180/270 and confidence ≥ `OSD_MIN_CONFIDENCE` (2.0); any failure keeps the image | returns the image unchanged, rotation 0 |
| `read(image: bytes) -> str` | `tesseract stdin stdout -l fin+eng --psm 4`, 120 s timeout; non-zero exit, `OSError` or timeout → `OcrError` | fixed text |

`TesseractOcrEngine.__init__` gets a second injectable runner, `run_image` (args, stdin
bytes → `CompletedProcess[bytes]`), next to the existing `run` used by `check()`. The
evaluation tool's runner already has this signature. `Oriented` and `OcrError` move here
from `evaluation/ocr.py`.

**`ReceiptModel`** gains `generate(prompt: str, schema: dict[str, Any]) -> str`, the raw
`response` text. Categorization will use the same method with its own prompt.

`OllamaReceiptModel.generate` sends `POST /api/generate`:

```json
{"model": "<RRMC_MODEL>", "prompt": "...", "format": {...}, "stream": false,
 "options": {"temperature": 0, "num_ctx": 8192}, "keep_alive": -1}
```

`num_ctx` 8192 as in the evaluation (Ollama's default context can cut a long OCR text
without an error). `keep_alive` −1 keeps the model loaded (FR-30). The timeout is
`GENERATE_TIMEOUT_SECONDS = 300.0`; Ollama sends nothing until it is done when `stream` is
false, so the read timeout is the time of the answer.

| Ollama outcome | Error |
|---|---|
| `httpx2.ConnectError`, `ConnectTimeout`, other `TransportError` | `ModelUnavailableError` |
| HTTP 404 (model not pulled) | `ModelUnavailableError` |
| `ReadTimeout`, `WriteTimeout`, `PoolTimeout` | `ModelTimeoutError` |
| other HTTP error status; body is not `{"response": str}` | `ModelAnswerError` |
| `is_cloud_model(model)` | `ModelUnavailableError`, no request (AC21) |

The client is built with `trust_env=False` for every call (AC23). `is_cloud_model(name)` is
true when the name ends in `-cloud` or `:cloud` (compared case-insensitively, as the
evaluation tool does). Exception messages name no prompt or answer.

`FakeReceiptModel.generate` returns a fixed valid answer. It is used only by engine tests;
the fake reader does not call it.

### Import

`process_file(path, *, store, repository, reader, folders, now)`:

- After the duplicate check and before choosing the done name: `read = reader.read(data)`;
  `ReadFailedError` → `_FileFailedError(error.reason)` (moves to the failed folder).
- `ModelUnavailableError` is re-raised before the generic `except Exception`, so it is not
  turned into `internal_error` and the file is not moved.
- The transaction stores `repository.add(hash, target, now, store=..., purchase_date=...,
  total_cents=..., ocr_text=...)` and `repository.add_line(receipt_id, position, name,
  amount_cents, is_deposit_refund)` for each line, positions from 1. Any `sqlite3.Error`
  → `save_failed`; the transaction rolls back the receipt and its lines (AC16).
- A failed move deletes the receipt; its lines go with it (`ON DELETE CASCADE`, AC17).

`FailureReason` gets `unreadable_image`, `ocr_failed`, `no_text`, `parse_failed`.

`ImportService` gets `engines: Engines` and `reader: ReceiptReader` (main.py passes the ones
it already creates). `start()`:

1. Under the lock: refuse when running (409), check the folders (503
   `folders_unavailable`).
2. Outside the lock, so `GET /api/import` never waits for Ollama: `ocr.check()` not `ok` →
   `OcrNotReadyError` (503 `ocr_unavailable`); `is_cloud_model(settings.model)` or
   `model.check()` not `ok` → `ModelNotReadyError` (503 `model_unavailable`).
3. Under the lock again: refuse when a run started meanwhile (409), list the folder, set
   `running`.

`_run` catches `ModelUnavailableError` from `process_file`: the current and remaining files
are not recorded and stay in the import folder; the state gets `stopped =
{"reason": "model_unavailable", "message": texts.MODEL_LOST}`; the run finishes. Log line:
`Import stopped: model unavailable, imported=%d duplicates=%d failed=%d`. `stopped` is
`None` otherwise, and in `idle`.

### Data model: migration `0003_receipt_reading.sql`

```sql
ALTER TABLE receipts ADD COLUMN store TEXT;            -- NULL for receipts imported before reading
ALTER TABLE receipts ADD COLUMN purchase_date TEXT     -- YYYY-MM-DD, NULL when not read
    CHECK (purchase_date IS NULL OR purchase_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]');
ALTER TABLE receipts ADD COLUMN total_cents INTEGER;   -- integer cents (NFR-6)
ALTER TABLE receipts ADD COLUMN ocr_text TEXT;         -- raw Tesseract output (FR-10)

CREATE TABLE receipt_lines (
    id                INTEGER PRIMARY KEY,
    receipt_id        INTEGER NOT NULL REFERENCES receipts (id) ON DELETE CASCADE,
    position          INTEGER NOT NULL CHECK (position >= 1),   -- printed order, from 1
    name              TEXT NOT NULL CHECK (trim(name) <> ''),   -- as read
    amount_cents      INTEGER NOT NULL,                         -- net of discount, incl. deposit
    is_deposit_refund INTEGER NOT NULL CHECK (is_deposit_refund IN (0, 1)),
    CHECK (is_deposit_refund = 0 OR amount_cents < 0),
    UNIQUE (receipt_id, position)
);
```

Only nullable columns and a new table are added, so receipts already in the user's database
stay as they are. Categorization adds the category columns to `receipt_lines` later.

`ReceiptRepository`:

- `add(image_hash, file_name, imported_at, *, store=None, purchase_date=None,
  total_cents=None, ocr_text=None)`: existing callers and tests keep working.
- `add_line(receipt_id, position, name, amount_cents, is_deposit_refund)`.
- `ReceiptRow` gets `store`, `purchase_date`, `total_cents`, `ocr_text` (default `None`);
  `lines(receipt_id) -> list[LineRow]` for tests and the later review UI.

### API

`ImportStateOut` gets `stopped: StoppedOut | None` (`reason: Literal["model_unavailable"]`,
`message: str`). New `AppError`s in `receipt_import/errors.py`: `OcrNotReadyError`,
`ModelNotReadyError`. Texts in `app/texts.py`:

| Constant | Text |
|---|---|
| `UNREADABLE_IMAGE` | `Kuvaa ei voitu avata.` |
| `OCR_FAILED` | `Tekstin tunnistus epäonnistui.` |
| `NO_TEXT` | `Kuvasta ei löytynyt tekstiä.` |
| `PARSE_FAILED` | `Kuittia ei voitu tulkita.` |
| `MODEL_UNAVAILABLE` | `Kielimalli ei ole käytettävissä. Käynnistä Ollama ja tarkista mallin nimi.` |
| `OCR_UNAVAILABLE` | `Tekstintunnistus ei ole käytettävissä.` |
| `MODEL_LOST` | `Kielimalli ei vastaa. Tuonti pysäytettiin; jäljellä olevat kuvat jäivät tuontikansioon.` |

### Frontend

- `api/imports.ts`: the four reasons in `FailureReason`; `stopped: {reason:
  "model_unavailable"; message: string} | null` in `ImportState`; MSW fixtures in
  `src/test/imports.ts` get `stopped: null`.
- `ImportPage.tsx`: shows `stopped.message` in the report (as `role="status"` text inside
  the report region). A refused start and the failure messages already show the backend's
  `message` (`role="alert"` and the failures list); AC25 and AC27 get component tests.

### Evaluation tool (PC11)

- `evaluation/prompt.py` re-exports `ANSWER_SCHEMA`, `INSTRUCTIONS`, `Answer`,
  `AnswerLine`, `text_prompt`, `parse_answer` from `app.receipt_reading.prompt` and keeps
  `image_prompt` (vision only).
- `evaluation/ocr.py` re-exports `preprocess`, `exif_orientation`, `Oriented`, `OcrError`,
  `OSD_MIN_CONFIDENCE` and the Tesseract arguments; `TesseractOcr(run)` wraps
  `TesseractOcrEngine(run_image=run)`; `upright_original` stays (vision only).
- `evaluation/ollama.py` stays as it is (its own check messages and `keep_alive` "10m").
- All tests in `backend/tests/evaluation/` must pass without edits.

### Settings

`Settings.model` default and `.env.example` `RRMC_MODEL` become
`qwen3:30b-a3b-instruct-2507-q4_K_M`. The [foundation spec](foundation.md) AC6 names the old
default `qwen2.5:7b` (its PC3 calls it an example to be chosen here), so its PC3 and AC6 are
corrected first, and then `tests/unit/test_settings.py` follows the corrected AC. `.env` is not touched; the user changes their own
`RRMC_MODEL` and runs `ollama pull qwen3:30b-a3b-instruct-2507-q4_K_M` (documented in
`development.md`). No new setting: the time limits are constants.

### Dependencies

None to add. Pillow and `httpx2` are already backend dependencies; Tesseract with `fin` and
`eng` is already in the backend image.

### Check against the ACs

| AC | Covered by |
|---|---|
| AC1, AC2, AC5 | `preprocess` (moved unchanged) |
| AC3, AC4 | `TesseractOcrEngine.orient` |
| AC6, AC9, AC10, AC10b | `parse_answer` + `to_read_receipt` |
| AC7, AC11b, AC23 | `OllamaReceiptModel.generate` |
| AC8 | `parse_answer` |
| AC11, AC12 | `OcrReceiptReader` steps 1–3, `process_file` |
| AC13, AC14, AC16, AC17 | `process_file`, migration 0003, `ReceiptRepository` |
| AC15 | duplicate check stays before `reader.read` |
| AC18, AC19, AC21 | `ImportService.start` checks |
| AC20 | `ModelUnavailableError` through `process_file` to `_run`, `stopped` |
| AC22 | no new log line carries content; `log_without_message` for unexpected errors |
| AC24, AC24b | `FakeReceiptReader`, `create_reader` |
| AC25–AC27 | `ImportPage`, `api/imports.ts` |
| PC10 | settings default, `.env.example`, ADR 0003 |
| PC11 | evaluation wrappers; evaluation tests unchanged |

## Tasks

Each task is one Red → Green → Refactor cycle unless it says otherwise. New backend unit
tests go to `backend/tests/unit/receipt_reading/` or next to the existing ones
(`unit/engines/`, `unit/storage/`, `unit/receipt_import/`); API tests go to
`backend/tests/integration/test_import_reading_api.py`. After every task the backend (or
frontend) tests, lint, format check and type check pass. The tests in
`backend/tests/evaluation/` are never edited.

### Spec and settings

- [x] **T1 Default model (PC10).** Correct [foundation](foundation.md) PC3 and AC6 to the new
  default, with a note pointing here; then `tests/unit/test_settings.py` follows the
  corrected AC6 (Red), `Settings.model` default and `.env.example` (Green). Test:
  `test_settings.py` default case.

### Receipt reading: moved code

- [x] **T2 Preprocessing in the app (AC1, AC2, AC5).** Tests
  `test_ac1_exif_6_turns_and_scales`, `test_ac2_missing_or_broken_tag_is_not_turned`,
  `test_ac5_wide_image_is_not_downscaled`, and `UnreadableImageError` for undecodable bytes,
  in `unit/receipt_reading/test_preprocess.py`. Move `preprocess`, `exif_orientation` to
  `app/receipt_reading/preprocess.py`; `evaluation/ocr.py` re-exports them (PC11).
- [x] **T3 Prompt and schema in the app (AC8).** Test
  `test_ac8_answers_not_matching_the_schema_are_none` in `test_prompt.py`. Move
  `ANSWER_SCHEMA`, `INSTRUCTIONS`, `Answer`, `AnswerLine`, `text_prompt`, `parse_answer` to
  `app/receipt_reading/prompt.py`; `evaluation/prompt.py` re-exports them and keeps
  `image_prompt` (PC11).

### Engines

- [x] **T4 OCR orientation and reading (AC3, AC4, AC12).** Tests in
  `unit/engines/test_ocr.py`: `test_ac3_sure_osd_turns_the_image`,
  `test_ac4_unsure_or_failed_osd_keeps_the_image` (confidence 1.9, rotate 0, exit 1, bad
  output), `test_ac12_tesseract_error_or_timeout_is_ocr_error`; fake `orient` and `read`.
  Implement `orient`, `read`, `run_image`, `Oriented`, `OcrError` in `app/engines/ocr.py`;
  `evaluation/ocr.py` `TesseractOcr` wraps `TesseractOcrEngine(run_image=...)`.
- [x] **T5 Model generate call (AC7, AC11b, AC20, AC21, AC23).** Tests in
  `unit/engines/test_model.py` with `httpx2.MockTransport`:
  `test_ac7_generate_sends_the_reading_request`,
  `test_ac11b_read_timeout_is_model_timeout`,
  `test_ac20_connect_error_and_404_are_model_unavailable`,
  `test_http_500_or_bad_body_is_model_answer_error`,
  `test_ac21_cloud_model_is_refused_without_a_request`,
  `test_ac23_proxy_settings_are_ignored`. Implement `generate`, `is_cloud_model`, the three
  errors and `trust_env=False`; fake `generate`.

### Receipt reading: new code

- [x] **T6 Validation (AC6, AC9, AC10, AC10b).** Tests in `test_validation.py`:
  `test_ac6_valid_answer_becomes_a_read_receipt`, `test_ac9_rule_breaks_are_parse_failed`
  (no lines, blank name, negative total, refund with a positive amount),
  `test_ac10_not_a_real_date_is_none`, `test_ac10b_blank_store_is_empty`. Implement
  `receipt.py` and `validation.py`.
- [x] **T7 OCR reader (AC6, AC11, AC11b, AC12).** Tests in `test_reader.py` with engine
  doubles: valid path returns AC6 with the unstripped OCR text; undecodable image →
  `unreadable_image`; `OcrError` → `ocr_failed`; blank text → `no_text` and no model call;
  timeout, answer error, invalid JSON → `parse_failed`; `ModelUnavailableError` passes
  through. Implement `reader.py`.
- [x] **T8 Fake reader and factory (AC24, AC24b).** Tests in `test_fake.py`:
  `test_ac24_fake_returns_the_fixed_receipt`,
  `test_ac24b_listed_hash_is_parse_failed`, `test_create_reader_picks_fake_or_ocr`.
  Implement `fake.py`, `factory.py`.

### Storage

- [x] **T9 Migration and repository (AC13, AC16, AC17).** Tests in
  `unit/storage/test_receipt_repository.py` and `test_receipt_lines_schema.py` (temporary SQLite file): migration 0003 keeps existing receipts
  with `NULL` read fields; `add` with read fields and `add_line` round-trip through `lines`;
  CHECK constraints refuse a refund with a positive amount, a blank name and a bad date
  text; deleting a receipt deletes its lines; schema version is 3. Implement
  `0003_receipt_reading.sql` and the repository methods. Update `docs/datamodel.md`.

### Import

- [x] **T10 Reading step in `process_file` (AC11–AC17, AC22).** Integration tests in
  `integration/test_import_reading_api.py` through `POST`/`GET /api/import` with a reader double:
  `test_ac13_imported_receipt_has_read_data_and_lines`,
  `test_ac14_reading_failure_stores_nothing_and_run_goes_on`,
  `test_ac15_duplicates_are_not_read`, `test_ac11_unreadable_image`,
  `test_ac12_ocr_failure_and_no_text`, `test_ac11b_model_timeout_fails_only_that_image`,
  `test_ac10_date_stored_empty`, `test_ac16_failed_line_save_rolls_back`,
  `test_ac17_failed_move_removes_receipt_and_lines`. Implement the reading step, the new
  reasons and texts; `main.py` passes the reader.
- [x] **T11 Start checks (AC18, AC19, AC21).** Tests:
  `test_ac18_start_refused_when_model_unavailable` (`unavailable` and `missing_model`),
  `test_ac19_start_refused_when_ocr_unavailable`, `test_ac21_cloud_model_refused`, and a
  test that a run started during the checks gives 409. Implement the checks in `start()`,
  `OcrNotReadyError`, `ModelNotReadyError`.
- [x] **T12 Model lost during a run (AC20).** Test
  `test_ac20_model_lost_stops_the_run`: state counts, `stopped`, files and receipts as in
  AC20; `stopped` is `null` in `idle` and in a normal run. Implement `stopped` in
  `_run`, `ImportStateOut` and the stop log line.
- [x] **T13 Privacy and fakes end to end (AC22, AC24, AC24b).** Tests:
  `test_ac22_no_receipt_content_in_the_log` (markers in OCR text, answer, names and file
  names; `caplog` at DEBUG), `test_ac24_fake_engines_store_the_fixed_receipt_twice`,
  `test_ac24b_fake_parse_failed_image`. Fix anything they find.
- [x] **T14 Real Tesseract (AC1, AC3).** Test marked `tesseract`, like
  `tests/evaluation/test_eval_tesseract.py`: a synthetic receipt rendered by Pillow, stored sideways with EXIF 6, and
  one rotated without EXIF; `OcrReceiptReader` steps 1–2 give OCR text with the rendered
  words. No model.

### Frontend

- [x] **T15 Tuonti page (AC25, AC26, AC27).** Component tests in `ImportPage.test.tsx`
  with MSW: `AC25 refused start shows the message and enables the button`,
  `AC26 stopped run shows its message`, `AC27 new failure reasons show their messages`.
  Implement the types in `api/imports.ts`, `stopped` in the fixtures and the page.
- [x] **T16 E2E (AC13, AC24, AC24b, AC27).** Extend `frontend/e2e/import.spec.ts` with the
  parse failure journey (`FAKE_PARSE_FAILED_IMAGE` bytes as `parse-failed-<run>.png`); the
  existing journey stays green. Run `docker compose --profile e2e run --rm e2e`.

### Documentation and close

- [x] **T17 Docs.** Update `docs/subsystems/receipt-reading/README.md` (full subsystem),
  `import` and `ui` READMEs, `docs/api-reference.md` (`stopped`, new errors and reasons),
  `docs/architecture.md` (open question 4 resolved, interfaces), `docs/glossary.md` (read
  receipt, receipt reader), `docs/development.md` and `AGENTS.md` (`ollama pull` of the new
  model), `docs/content-plan.md`, PRD (FR-8 note, FR-29, open question 4 resolved), and
  `specs/README.md`. Check every relative link.
- [x] **T18 Full verification.** Run every command in
  [development.md](../../docs/development.md#commands) for backend, frontend, E2E and
  container tests; check backend coverage of `receipt_reading` and the changed import code
  (≥ 90 % lines); record "Changes during implementation" in this spec; hand over to
  `review-audit`.

## Changes during implementation

Recorded 2026-10-30. None changes an AC.

- **Health takes a narrower model protocol.** `ReceiptModel` got `generate()`. `ModelLoader`
  only needs `check()` and `load()`, so they became `LoadableModel`, which `ReceiptModel`
  extends; the health test double needed no change (@backend/app/health/service.py).
- **Existing tests that the new behavior made outdated,** each following an AC of this spec:
  foundation AC6 (default model; `test_settings.py`, and `test_health.py`, which uses the
  default settings), the receipt-import tests that compared a whole receipt row or the whole
  idle state (`test_import_run.py` AC1 now compares the image record fields;
  `test_import_api.py` idle state has `stopped: null`; `test_receipts_schema.py` AC1 allows
  later columns, as the catalog test does), and the test doubles `run_file` (passes the fake
  reader) and `FailingRepository` (passes the read fields on, can fail a line). The tests in
  `backend/tests/evaluation/` are unchanged and pass.
- **`ImportStateOut.stopped` has the default `None`,** so code that builds a state without it
  stays valid; the API always returns the field.
- **The E2E journey of AC13/AC24 checks the UI only** (`Tuotu: 1`); the stored fake data is
  checked by `test_ac24_fake_engines_store_the_fixed_receipt_twice`.
- **The T14 real Tesseract test** (`tests/integration/test_reading_tesseract.py`) verifies code
  written in T2 and T4, so it had no Red step.
- **The E2E backend image was stale** (built before Pillow was a dependency) and had to be
  rebuilt with `docker compose --profile e2e build backend-e2e`.

### Verification (2026-10-30)

| Command | Result |
|---|---|
| `docker compose run --rm backend pytest` | 612 passed |
| `docker compose run --rm backend pytest -m tesseract` | 4 passed |
| `docker compose run --rm backend sh -c "ruff check . && ruff format --check ."` | passed |
| `docker compose run --rm backend pyright` | 0 errors |
| Backend coverage of `receipt_reading`, `receipt_import`, `engines`, `receipt_repository` | 99 % lines (the two uncovered lines are the real subprocess calls) |
| `docker compose run --rm frontend npm test` | 82 passed |
| `docker compose run --rm frontend npm run lint`, `npm run typecheck` | passed |
| `docker compose run --rm frontend npm run format:check` | the changed files pass; untouched files fail only because their working copy has CRLF line endings (`core.autocrlf=true`) |
| `docker compose --profile e2e run --rm e2e` | 6 passed |
| `scripts/container-tests.ps1` | all passed |

## Audit

Audited 2026-10-30, verdict PASS after one fix cycle. An independent reviewer read the code
against this spec; its findings were checked in the code before acting on them.

- Acceptance criteria: 30/30 met (AC1–AC27 with AC10b, AC11b, AC24b); every AC has a test
  whose name carries its ID.
- Tests: backend 612 passed and 4 real Tesseract tests passed; 99 % lines in
  `receipt_reading`, `receipt_import`, `engines` and the receipt repository (target 90 %;
  the two uncovered lines are the real subprocess calls). Frontend 82 passed, 100 % lines in
  the Tuonti page and the import client. E2E 6 passed, twice in a row. Container tests
  passed. Lint, format and type checks clean; no skipped or TODO tests.
- Security: no findings. No receipt content in logs or errors (AC22 runs at DEBUG); SQL is
  parameterized; no external calls (cloud models refused, `trust_env=False`); test data is
  synthetic. `npm audit` 0 vulnerabilities. `pip-audit` is not in the backend image and was
  not run, because installing it would send the dependency list to an outside service.
- Docs: the receipt-reading, import, storage and UI READMEs, `datamodel.md`,
  `api-reference.md`, `architecture.md`, `glossary.md`, `development.md`, `content-plan.md`,
  PRD, `AGENTS.md` and ADR 0003 updated; a scan found no undocumented module and no reference
  to a missing file.
- Fixed in the audit (see [learnings](../../docs/learnings.md)): the AC23 proxy test could
  not fail, because `httpx2` sends to a given mock transport even with `trust_env=True`; it
  now checks the client's setting, and a mutation makes it fail. The AC11b integration test
  scripted a reading failure instead of a timeout and did not check `stopped`; it now runs the
  OCR reader with a model that times out, and a mutation makes it fail. `evaluation/ocr.py`
  re-exports `OSD_MIN_CONFIDENCE`, `OSD_ARGS` and `TESSERACT_ARGS` as the Plan said. The API
  reference says `no_text` covers whitespace-only text.
- Later:
  - A Pillow error outside the caught types (or a huge image in `orient`) gives
    `internal_error` instead of `unreadable_image`.
  - The 300 s model timeout is also the connect timeout, so silently dropped packets stop a
    run only after 300 s (a refused connection stops it at once).
  - `httpx2` `TooManyRedirects` and `DecodingError` from Ollama give `internal_error`.
  - The evaluation tool's OSD-rotated image no longer keeps an ICC profile, and Pillow
    `ValueError`/`SyntaxError` in preprocessing now count as `ocr_error`; results are
    practically the same and its tests are unchanged.
  - The evaluation tool's `test_ac19_proxy_settings_are_ignored` has the same weakness as
    AC23 had.
- Not part of this change: untouched files whose working copy has CRLF line endings
  (`core.autocrlf=true`) make `npm run format:check` warn; Git stores them with LF.

## Range rule (after the audit)

The audit found that a total or amount outside SQLite's signed 64-bit integer range failed
the image as `internal_error` (Python raises `OverflowError` when binding it, which is not
a `sqlite3.Error`). The user decided to make it a validation rule: `t` must be ≤ 2^63 − 1
and each `a` from −2^63 to 2^63 − 1, otherwise `parse_failed` (Validation table, AC9).
The check belongs in `to_read_receipt`, so nothing reaches storage.

- [x] R1: AC9 unit tests for `t` = 2^63 and `a` = −2^63 − 1 fail first; then the check in
  @backend/app/receipt_reading/validation.py; the rules table in
  `docs/subsystems/receipt-reading/README.md` updated.
- Verified 2026-10-30: the two new AC9 cases failed first (`DID NOT RAISE`), then passed;
  a test that values exactly at the limits are kept was added. Backend `pytest` 615 passed;
  `ruff check`, `ruff format --check` and `pyright` clean.
