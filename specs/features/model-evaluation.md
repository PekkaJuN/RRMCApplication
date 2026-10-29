# Feature: Model evaluation

## Overview
- **Status:** Done (change: [Image orientation](#change-image-orientation-2026-10-29))
- **Created:** 2026-10-28
- **Updated:** 2026-10-28: approved by the user; detail files moved to one folder per variant
  (PC7, AC5, AC6), because several variants would write the same `<index>.json`; Plan added;
  AC12 covers OCR failures (`ocr_error`), approved by the user during implementation;
  audit: AC9 refuses repeated variants, AC12 adds `image_error`, new AC21 (exit code 3),
  criteria compared on exact shares (approved by the user).
  2026-10-29: images are turned upright before OCR, from EXIF and from Tesseract's
  orientation detection, and `vision:` images from EXIF (PC4, PC7, AC22–AC26), after the
  first real run; approved by the user
- **Depends on:** [Project foundation](foundation.md), [Receipt import](receipt-import.md)
- **Implements:** the comparison asked for by PRD open question 4 (Tesseract + text model
  against a vision model on 20–30 real receipts), measured against NFR-8 (3 minutes per
  receipt). A development tool, not an app feature: it adds no endpoint, page or table.
- **Affected subsystems:** none of the app's subsystems. A new tool package
  `backend/evaluation/` (documented in [development.md](../../docs/development.md)).

## Problem Statement
The receipt-reading spec must choose how a receipt image becomes structured data: OCR with
Tesseract followed by a text model, or a vision model that reads the image directly, and
which model size. The model runs on the CPU (PRD open question 1), so the choice trades
accuracy against time. It can only be made by measuring on real receipts, and real receipts
must never leave the user's computer (AGENTS.md, Guardrails). The user therefore needs a tool
that runs the candidates locally, compares them with answers the user has written down, and
prints only aggregate numbers that can be shared without revealing any receipt content.

## Current Behavior
None (new). What exists:

- Tesseract with `fin` and `eng` in the backend image; `OcrEngine` has only `check()`
  ([receipt-reading](../../docs/subsystems/receipt-reading/README.md)).
- Ollama on Windows at `RRMC_OLLAMA_URL`; `qwen2.5:7b` is pulled. Measured speed: prompt 61
  tokens/s, output 9.6 tokens/s (PRD open question 1).
- `source/` is ignored by Git, so files under it never enter the repository.

## Proposed Change

### Concepts

- An **evaluation folder** holds the user's receipt images and, next to each image, a
  **truth file**: the values the user reads from the paper receipt. Default
  `source/eval/`, setting `RRMC_EVAL_DIR`.
- A **variant** is one way to read a receipt:
  - `ocr:<model>`: preprocess the image, run Tesseract (`fin+eng`), send the text to the
    text model `<model>`;
  - `vision:<model>`: send the image to the vision model `<model>`.
- An **evaluation run** runs one or more variants over the receipts and writes its results
  under `<evaluation folder>/results/<run id>/`, where the run id is the start time
  `YYYYMMDD-HHMMSS`.

### Parts

- **PC1 Truth file template.** `init` creates `<image name>.truth.json` with empty values
  for every JPEG or PNG image in the evaluation folder that has none. It never overwrites a
  file.
- **PC2 Truth file format.**
  ```json
  {
    "store": "",
    "date": "YYYY-MM-DD",
    "total_cents": 0,
    "line_count": 0,
    "lines": []
  }
  ```
  `store`, `date`, `total_cents` and `line_count` are required. `lines` is optional: when the
  user fills it, each item is `{"name": "...", "amount_cents": 125}` with the amount as
  printed after merging any discount and deposit into the item (PRD FR-9); a deposit refund
  (panttipalautus) is its own line with a negative amount. A receipt whose truth file has
  `lines` belongs to the **full subset**.
- **PC3 Variants.** `run` takes one or more `--variant` options. Each variant may be
  limited with `--limit N` (the first N receipts in name order) or `--subset full`. A model
  name ending in `-cloud` or `:cloud` is refused, because Ollama would send the data to a
  cloud service.
- **PC4 Reading.** Every variant asks for the same compact JSON, with Ollama's structured
  output (`format` set to the JSON schema) and temperature 0:
  ```json
  {"s": "store", "d": "YYYY-MM-DD", "t": 1234, "l": [{"n": "name", "a": 125, "r": false}]}
  ```
  `t` and `a` are integer cents, `r` is true for a deposit refund line. The instructions in
  the prompt state the Finnish receipt rules of PRD FR-9. The prompt text is the same for
  both kinds of variant, apart from where the receipt comes from (OCR text or image).
  Preprocessing for `ocr:` variants, in this order:
  1. **EXIF orientation:** the image is turned upright as its EXIF orientation tag (values
     1–8) says. An image without the tag is left as it is; so is an image whose tag cannot
     be read or has a value outside 1–8, which is recorded as no tag.
  2. Grayscale, upscaling so the image is at least 1 500 pixels wide, and automatic contrast.
  3. **Orientation detection:** Tesseract's orientation and script detection (OSD) runs on
     the preprocessed image. When it reports a rotation of 90, 180 or 270 degrees with an
     orientation confidence of at least `OSD_MIN_CONFIDENCE` (2.0, one constant in the
     code), the image is rotated upright before OCR. A rotation of 0, a lower confidence, or
     a failed detection (for example too little text) leaves the image as it is and is not
     an error.

  The time of all three steps counts in `seconds`. OSD catches images whose EXIF tag is
  missing or wrong (scans, edited images, a phone held flat above the receipt). OSD needs
  enough text: on synthetic receipts it failed with two lines and reported a confidence
  below 1.5 with eight, but 2.5–4.6 with 20 or more lines, always with the right rotation.

  For `vision:` variants only step 1 applies: an image whose EXIF orientation tag is 2–8 is
  turned upright and sent in its own format (JPEG at quality 95, also for an MPO file, the
  multi-picture JPEG of Ultra HDR phone photos; PNG lossless) with original colors and size
  and its color profile kept; an image without the tag, or with tag 1, is sent as the
  original file.
- **PC5 Scoring.** For each receipt and variant (see [Metrics](#metrics)).
- **PC6 Report.** At the end the tool prints, and saves as `summary.md` in the run folder,
  one row per variant with the aggregate metrics and whether the variant meets the
  [decision criteria](#decision-criteria). During the run it prints progress as
  `<variant> <n>/<total> <seconds> s`. Neither contains file names or receipt content.
- **PC7 Local details.** Per receipt and variant, the run folder gets
  `<variant folder>/<index>.json` (the variant with `:` replaced by `-`, e.g.
  `ocr-qwen2.5-7b/1.json`; the index is the receipt's position in name order, the same for
  every variant) with the OCR text, the model's raw answer, the parsed answer, the scores and the times, so the user
  can look at failures on their own computer. For `ocr:` variants it also holds
  `"orientation": {"exif": <tag value or null>, "osd_rotation": <0, 90, 180 or 270>,
  "osd_confidence": <number or null>}`; `osd_rotation` is the rotation applied, and
  `osd_confidence` is `null` when the detection failed. `vision:` variants have
  `"orientation": {"exif": <tag value or null>}`. The run folder is under the evaluation folder,
  which is ignored by Git.
- **PC8 Running.** The tool runs in a Compose service `eval` (profile `eval`) built from the
  backend image, with the evaluation folder mounted and the settings file read as for the
  backend. It needs no port and talks only to `RRMC_OLLAMA_URL`.

### Metrics

| Metric | Per receipt | Aggregate |
|---|---|---|
| `valid` | The answer is JSON that matches the schema | % of receipts |
| `total` | `t` equals `total_cents` | % of valid receipts |
| `date` | `d` equals `date` | % of valid receipts |
| `store` | The normalized store names are equal, or one contains the other | % of valid receipts |
| `consistent` | The sum of `a` equals `t` | % of valid receipts |
| `lines` | The number of lines equals `line_count` | % of valid receipts |
| `amounts` (full subset) | F1 of the line amounts as multisets against `lines` | mean |
| `names` (full subset) | For lines matched by amount, the mean name similarity (0–1, `difflib` ratio of normalized names) | mean |
| `seconds` | Wall time of OCR + model | median (mean of the two middle values for an even count), 90th percentile (nearest rank), max |
| `in_time` | `seconds` ≤ 180 | % of receipts |

An invalid answer counts as wrong for every metric except `seconds`. Normalization of names
is the catalog's normalization ([names](../../docs/subsystems/categorization/README.md#names)).
Percentages are rounded to whole numbers; similarity and F1 to two decimals.

### Decision criteria

A variant **meets the criteria** when `valid` = 100 %, `total` ≥ 90 %, `date` ≥ 95 %, and
`in_time` ≥ 90 %, compared on the exact shares, not on the rounded percentages (199 valid of
200 is not 100 %). The constants live in one place in the code. The choice itself is not made
by the tool: the user and the receipt-reading spec choose, and the result is recorded as an
ADR with the aggregate numbers only.

### Commands

```powershell
# Create truth file templates for new images
docker compose --profile eval run --rm eval python -m evaluation init
# Compare variants
docker compose --profile eval run --rm eval python -m evaluation run `
  --variant ocr:qwen2.5:7b `
  --variant ocr:qwen2.5:14b --subset full `
  --variant vision:qwen2.5vl:7b --limit 5
```

### Out of Scope
- Changes to the app: no endpoint, page, table or change to the import run. The
  receipt-reading spec builds the real reading step and may reuse code from this tool through
  its own spec.
- Categorization of lines (FR-12): the model is not asked for categories.
- A UI for writing truth files; the user edits the JSON by hand.
- Other OCR engines, cloud services and models not served by the local Ollama.
- Choosing the variant automatically, or tuning prompts automatically.
- Weighed items, quantities and unit prices as separate scores: they are part of the line's
  amount.

## Acceptance Criteria

All files in the ACs are synthetic. "The tool" is `python -m evaluation` in the `eval`
service; in tests, OCR and the model are deterministic fakes unless an AC says otherwise.

### Truth files

#### AC1: Templates for new images
**Given** the evaluation folder holds `a.jpg`, `b.png`, `c.txt` and `b.png.truth.json` with
`{"store": "X", "date": "2026-01-02", "total_cents": 5, "line_count": 1}`
**When** the user runs `init`
**Then** `a.jpg.truth.json` is created with exactly the template of PC2, `b.png.truth.json`
is unchanged, no file is created for `c.txt`, and the tool prints `Created 1 template(s).`

#### AC2: Invalid truth file
**Given** `a.jpg.truth.json` has `total_cents` `"12,50"` (a string), and `b.jpg.truth.json` is valid
**When** the user runs `run`
**Then** before any model call the tool prints
`Invalid truth file a.jpg.truth.json: total_cents must be an integer` and exits with code 2

#### AC3: Images without a truth file are skipped
**Given** `a.jpg` has a truth file and `b.jpg` has none
**When** the run finishes
**Then** only `a.jpg` is evaluated, and the report says `Skipped without truth file: 1`

#### AC4: A template that was not filled in
**Given** `a.jpg.truth.json` is still the unchanged template of PC2
**When** the user runs `run`
**Then** it is treated as AC3: skipped and counted under `Skipped without truth file`

### Running

#### AC5: OCR variant
**Given** `a.jpg` with a valid truth file and the variant `ocr:qwen2.5:7b`
**When** the run finishes
**Then** the image was preprocessed and passed to OCR with languages `fin+eng`, the OCR text
was sent to model `qwen2.5:7b` with the schema of PC4 as `format` and temperature 0, and
`results/<run id>/ocr-qwen2.5-7b/1.json` holds the OCR text, the raw answer, the parsed answer, the scores
and the times

#### AC6: Vision variant
**Given** `a.jpg` with a valid truth file and the variant `vision:qwen2.5vl:7b`
**When** the run finishes
**Then** OCR was not called, the image was sent to model `qwen2.5vl:7b` (base64 in `images`)
with the same schema, temperature 0 and the same instructions, and
`vision-qwen2.5vl-7b/1.json` has `ocr_text` `null`

#### AC7: Limit and subset
**Given** five receipts with truth files, two of them with `lines`
**When** the user runs `--variant ocr:m --limit 3 --variant ocr:n --subset full`
**Then** `ocr:m` evaluates the first three receipts in name order and `ocr:n` the two
receipts with `lines`

#### AC8: Cloud models are refused
**Given** any evaluation folder
**When** the user runs `run --variant ocr:gpt-oss:120b-cloud` or `--variant vision:x:cloud`
**Then** the tool prints `Cloud models are not allowed: <variant>` and exits with code 2
without calling Ollama

#### AC9: Malformed or repeated variant
**Given** any evaluation folder
**When** the user runs `run --variant qwen2.5:7b` (no kind) or `--variant audio:x`
**Then** the tool prints `Invalid variant: <value> (expected ocr:<model> or vision:<model>)`
and exits with code 2
**When** two variants have the same detail folder (`--variant ocr:m --variant ocr:m`, or
`ocr:a:b` and `ocr:a-b`)
**Then** the tool prints `Duplicate variant: <second value>` and exits with code 2 without
calling Ollama

#### AC10: Model not available
**Given** Ollama does not answer, or has not pulled a variant's model
**When** the user runs `run`
**Then** before the first receipt the tool prints `Ollama is not reachable at <url>` or
`Model <name> is not pulled. Run: ollama pull <name>` and exits with code 1

#### AC11: Invalid model answer
**Given** the model answers `not json`, or JSON without `t`
**When** that receipt is scored
**Then** `valid` is false, every accuracy metric of that receipt counts as wrong, its time is
counted, and the run goes on with the next receipt

#### AC12: Model call or OCR fails, or times out
**Given** one model call fails with an HTTP error or takes longer than 600 seconds; or the
image file cannot be read; or, for an `ocr:` variant, the image cannot be opened or
preprocessed or Tesseract fails
**When** that receipt is scored
**Then** it is scored as in AC11, its detail file records `"error": "timeout"`,
`"error": "model_error"`, `"error": "image_error"` or `"error": "ocr_error"`, and the run
goes on

### Orientation

The images in these ACs are PNG files drawn with Pillow, so rotations are lossless and two
images can be compared pixel for pixel.

#### AC22: EXIF orientation
**Given** an upright synthetic receipt image `U` (taller than wide), and the same image
stored turned so that its EXIF orientation tag says 6 (also 3 and 8)
**When** the turned image is preprocessed
**Then** the result equals the preprocessed `U` pixel for pixel, and the detail file of an
`ocr:` variant records `"exif": 6` (3, 8)

#### AC23: No EXIF orientation
**Given** an image without an EXIF orientation tag
**When** it is preprocessed
**Then** it is not turned (the result is grayscale, ≥ 1 500 pixels wide, with automatic
contrast, as before this change), and the detail file records `"exif": null`

#### AC24: Rotation from orientation detection
**Given** OSD reports a rotation of 90 (also 180 and 270) with orientation confidence 5.0
**When** an `ocr:` variant reads the receipt
**Then** OCR receives the preprocessed image turned upright by that rotation, and the detail
file records `"osd_rotation": 90, "osd_confidence": 5.0`
**And**, with the real Tesseract, a synthetic receipt of 20 lines drawn upright (the first
`MAITO 1,25`), turned 90 degrees and stored without an EXIF tag, gives OCR text that
contains `MAITO` and `1,25`, and `osd_rotation` is 90 or 270

#### AC25: Detection not used
**Given** OSD reports a rotation of 90 with orientation confidence 1.5; or OSD reports a
rotation of 0; or OSD fails (Tesseract exits with a non-zero code, or its output has no
rotation)
**When** an `ocr:` variant reads the receipt
**Then** OCR receives the preprocessed image without a further turn, the detail file
records `"osd_rotation": 0` and the reported confidence (`null` when OSD failed), no
`ocr_error` is recorded, and the run goes on

#### AC26: Vision image turned from EXIF
**Given** a `vision:` variant, and a synthetic JPEG whose EXIF orientation tag is 6
**When** the receipt is read
**Then** the model receives a JPEG that, opened, has the upright size (height and width
swapped against the stored image) and no orientation tag, and the detail file records
`"orientation": {"exif": 6}`
**Given** the same image without the tag
**When** the receipt is read
**Then** the model receives the original file bytes unchanged, and the detail file records
`"orientation": {"exif": null}`

### Scoring

#### AC13: Exact fields
**Given** truth `{"store": "K-Market Esimerkki", "date": "2026-01-02", "total_cents": 1185, "line_count": 4}`
and the answer `{"s": "K-MARKET  ESIMERKKI OY", "d": "2026-01-02", "t": 1185, "l": [four lines summing to 1185]}`
**When** it is scored
**Then** `valid`, `total`, `date`, `store`, `consistent` and `lines` are all true

#### AC14: Wrong values
**Given** the truth of AC13 and an answer with `t` 1158, `d` `"2026-02-01"`, store
`"S-Market"` and three lines summing to 1000
**When** it is scored
**Then** `valid` is true and `total`, `date`, `store`, `consistent` and `lines` are false

#### AC15: Line amounts and names on the full subset
**Given** truth lines amounts `[125, 249, 212, 599]` with names `MAITO 1L`, `LEIPÄ`, `OMENA`,
`KAHVI 500G`, and answer lines `[125 "Maito 1l", 249 "LEIPA", 599 "KAHVI 500G", 300 "X"]`
**When** it is scored
**Then** `amounts` is 0.75 (precision 3/4, recall 3/4), and `names` is the mean similarity of
the three matched pairs, each computed on normalized names (`"maito 1l"`/`"maito 1l"` is
1.0)

#### AC16: Deposit refund line
**Given** truth lines include `{"name": "PANTTIPALAUTUS", "amount_cents": -40}` and the answer
has a line with `a` -40 and `r` true
**When** it is scored
**Then** the -40 line matches in `amounts`, and it is part of `consistent` (the sum of all
`a`, refunds included, equals `t`)

#### AC17: Aggregates and criteria
**Given** a variant scored on 10 receipts: all valid, 9 totals right, 10 dates right, times
`[60, 70, …]` with 9 of 10 at most 180 s
**When** the report is made
**Then** its row shows `valid 100 %`, `total 90 %`, `date 100 %`, `in_time 90 %`, the median,
90th percentile and maximum seconds, and `meets criteria: yes`; with 8 totals right it shows
`total 80 %` and `meets criteria: no`

### Privacy

#### AC18: Report and progress contain no receipt content
**Given** receipts whose file names, truth values, OCR text and answers contain the marker
`SECRET-CONTENT`
**When** the run finishes
**Then** neither the printed output nor `summary.md` contains `SECRET-CONTENT` or any file
name; details with content exist only in the run folder under the evaluation folder

#### AC19: Only the local Ollama is called
**Given** `RRMC_OLLAMA_URL` is `http://host.docker.internal:11434`
**When** a run calls the model
**Then** every HTTP request goes to that base URL, and no other host is contacted

#### AC21: Unexpected error
**Given** an error the tool does not expect happens during a run
**When** it stops the run
**Then** the tool prints only `Evaluation failed: <error type>` (no traceback, no message,
no file name) and exits with code 3; detail files already written stay

#### AC20: Results stay out of Git
**Given** the default evaluation folder `source/eval/`
**When** `git check-ignore` is asked about `source/eval/a.jpg`,
`source/eval/a.jpg.truth.json` and `source/eval/results/x/summary.md`
**Then** all three are ignored

## Files to Modify
| File | Change |
|---|---|
| `backend/evaluation/` | New package: truth files, variants, preprocessing, OCR and Ollama calls, scoring, report, CLI (`python -m evaluation`) |
| `backend/tests/evaluation/` | Unit tests with synthetic data and fakes |
| `backend/pyproject.toml`, `backend/uv.lock` | Pillow for preprocessing (and later for receipt reading), if the Plan confirms it |
| `compose.yaml` | Service `eval` (profile `eval`), evaluation folder mount |
| `.env.example` | `RRMC_EVAL_DIR=./source/eval` |
| `docs/development.md` | How to prepare truth files and run an evaluation; privacy rules for sharing results |
| `docs/architecture.md` | Folder structure: `backend/evaluation/` as a development tool |
| `docs/content-plan.md` | Note in Gaps and open items |
| `docs/glossary.md` | Evaluation folder, truth file, variant, full subset |
| `AGENTS.md` | Layout: profile `eval`, `source/eval/` |
| `scripts/container-tests.ps1` | AC20 check, alongside the existing ignore checks |
| `specs/README.md` | Row for this spec |

## Risk
- **What could break:** nothing in the app; the tool is a separate package and Compose
  profile. The backend image grows by Pillow if it is added.
- **Privacy:** the tool handles real receipts by design. Mitigations: results stay under the
  ignored evaluation folder; the printed output and `summary.md` have aggregates only
  (AC18); cloud models are refused (AC8); only `RRMC_OLLAMA_URL` is called (AC19). The user
  shares only `summary.md`.
- **Time:** a full run of three variants on 25 receipts can take one to two hours on the CPU.
  `--limit` and `--subset` keep the slow variants short.
- **Validity:** 20–30 receipts give rough percentages (one receipt is 3–5 points). The
  decision criteria are a guide for the choice, not a guarantee.
- **Orientation (AC22–AC25):** OSD can choose a wrong rotation on a receipt with little or
  unusual text; the confidence limit keeps such cases unturned, and the detail file shows
  what was applied, so a wrong turn can be found. OSD adds about one to two seconds per
  receipt. It needs Tesseract's `osd` data, which is in the backend image
  (`tesseract --list-langs` shows `osd`). Results of runs before this change are not
  comparable for `ocr:` variants. Rollback: revert the change to `ocr.py`; nothing is stored.
- **Rollback:** delete the package, the service and the setting; the evaluation folder is the
  user's and is never deleted by the tool or by an agent.
- **Dependencies:** Tesseract (backend image), Ollama with the models the user pulls.

## Testing Strategy (MANDATORY)

### Unit tests (backend, pytest)
| AC | Function | Case | Given | When | Then | Mocks |
|---|---|---|---|---|---|---|
| AC1 | `init_templates` | new, existing, other files | folder of AC1 | init | one template, others untouched | temp folder |
| AC2 | `load_truth` | invalid type | `total_cents` "12,50" | load | error naming the file and field | temp folder |
| AC3, AC4 | `collect_receipts` | missing and unfilled truth | folder | collect | evaluated list and skipped count | temp folder |
| AC7 | `select_receipts` | limit, full subset | five receipts | select | as in AC7 | none |
| AC8, AC9 | `parse_variant` | cloud, malformed, valid | values of AC8, AC9 | parse | error text, or kind and model | none |
| AC5 | `preprocess` | small image | 600 px wide synthetic image | preprocess | grayscale, ≥ 1 500 px wide | none |
| AC22, AC23 | `preprocess` | EXIF 3, 6, 8; no tag; tag 0 or 9; broken EXIF | synthetic PNG and JPEG with and without the tag | preprocess | equal to the preprocessed upright image with its top up; untouched otherwise; tag value reported, `null` for no, invalid or broken tag | none |
| AC24, AC25 | `TesseractOcr.orient` | rotation 90/180/270 at confidence 5.0; confidence 2.0 (the limit); confidence 1.5; NaN; rotation 0; OSD exit code 1; output without rotation; exception | fake run command answering OSD | orient | image passed to OCR turned or not; orientation values as in the ACs; no error | fake `RunCommand` |
| AC22–AC25 | `run_evaluation` | detail file | fake `Ocr` reporting an orientation | run | `orientation` object in `ocr:` detail files | fake OCR, fake model |
| AC26 | `upright_original`, `run_evaluation` | JPEG and MPO with tag 6; JPEG with a color profile; JPEG without tag, with tag 1, 0 or 9; broken EXIF; unreadable image | synthetic JPEG | run a `vision:` variant | turned JPEG without tag and with the profile, or the original bytes; `orientation` in the detail file; `image_error` | fake model |
| AC5, AC6 | `OllamaReader` | request body | fake HTTP transport | read OCR text; read image | model, `format`, `options.temperature` 0, prompt, `images` base64 | `httpx2.MockTransport` |
| AC10 | `check_models` | unreachable, missing | fake transport | check | messages of AC10 | `httpx2.MockTransport` |
| AC11, AC12 | `parse_answer`, `run_variant` | not JSON, missing `t`, HTTP error, timeout | fake model | run | invalid; error recorded; next receipt runs | fake model |
| AC13, AC14 | `score_receipt` | right and wrong fields | values of AC13, AC14 | score | as in the ACs | none |
| AC15, AC16 | `score_lines` | amounts, names, refund | values of AC15, AC16 | score | 0.75; similarities; refund matched | none |
| AC17 | `aggregate`, `meets_criteria` | 9/10 and 8/10 totals | scores of AC17 | aggregate | rows and yes/no | none |
| AC18 | `run` (whole tool) | secret marker | synthetic folder with the marker | run with fakes | stdout and `summary.md` without the marker or file names | fake OCR, fake model, `capsys` |
| AC19 | `OllamaReader` | base URL | settings URL | read | every request to that URL | `httpx2.MockTransport` |

### Integration tests
| AC | Scenario | Input | Expected output |
|---|---|---|---|
| AC5 | real Tesseract on a synthetic receipt image drawn with Pillow (`MAITO 1,25`, `YHTEENSÄ 1,25`) | `ocr:` variant with a fake model | OCR text contains `MAITO` and `1,25`; marked `tesseract`, runs in the backend container |
| AC24 | real Tesseract OSD on a 20-line synthetic receipt turned 90 degrees, without an EXIF tag | `TesseractOcr.orient` after `preprocess`, then `read` | OCR text contains `MAITO` and `1,25`; `osd_rotation` is 90 or 270; marked `tesseract` |
| AC1–AC18 | CLI end to end with fakes | `python -m evaluation init` and `run` on a temp folder | exit codes, files and output as in the ACs |
| AC20 | ignore rules | `git check-ignore` | ignored (in `scripts/container-tests.ps1`) |

### E2E tests
None: the tool has no UI.

### Coverage target
- Backend: 90 % lines for `backend/evaluation/`; scoring and the variant and truth file
  checks: every branch.

### Test data
- Synthetic only: truth files and answers written in the tests; images drawn with Pillow
  from made-up text. No real receipt is ever used as a fixture.
- Mocks: fake OCR and fake model for the run; `httpx2.MockTransport` for the Ollama client.

## Related Documentation (MANDATORY)
- PRD: [specs/PRD.md](../PRD.md) FR-6–FR-9, NFR-1, NFR-3, NFR-8, open questions 1 and 4
- Specs: [Project foundation](foundation.md), [Receipt import](receipt-import.md)
- Tier 1: [architecture.md](../../docs/architecture.md),
  [development.md](../../docs/development.md)
- Tier 2: [receipt-reading](../../docs/subsystems/receipt-reading/README.md),
  [categorization](../../docs/subsystems/categorization/README.md#names) (normalization)
- ADRs: [0001 technology stack](../../docs/adr/0001-tech-stack.md),
  [0002 Docker](../../docs/adr/0002-docker.md); the model choice will be a new ADR
- Development rules: `AGENTS.md` (Guardrails, Privacy and security)

## Open Questions
None. (2026-10-29: the user chose to turn `vision:` images upright from EXIF too, AC26;
results of earlier `vision:` runs are therefore not comparable either.)

## Plan

Spec approved: 2026-10-28. The tool follows the
[code standards](../../docs/development.md#code-standards) like the app, but lives outside
`app/`: it may import from `app` (settings, name normalization), and `app` never imports
from it.

### Components

| Part | File | Contents | ACs |
|---|---|---|---|
| P1 Truth files | `backend/evaluation/truth.py` | `Truth`, `TruthLine` (Pydantic, strict types); `TEMPLATE`; `init_templates(folder)`; `load_truth(path)` raising `TruthFileError(file, field, problem)`; `collect_receipts(folder) -> (receipts, skipped)` | AC1–AC4 |
| P2 Variants | `backend/evaluation/variants.py` | `Variant(kind, model)`, `parse_variant(text)` raising `VariantError`; `select_receipts(receipts, limit, subset)`; `folder_name(variant)` | AC7–AC9 |
| P3 Preprocessing and OCR | `backend/evaluation/ocr.py` | `preprocess(image_bytes) -> bytes` (Pillow: grayscale, upscale to ≥ 1 500 px wide with LANCZOS, `ImageOps.autocontrast`); `TesseractOcr.read(image_bytes) -> str` runs `tesseract stdin stdout -l fin+eng --psm 4`; `Ocr` protocol | AC5 |
| P4 Prompt and schema | `backend/evaluation/prompt.py` | `ANSWER_SCHEMA` (JSON schema of PC4), `INSTRUCTIONS` (the FR-9 rules), `text_prompt(ocr_text)`, `image_prompt()`; `Answer`, `AnswerLine` (Pydantic, strict) and `parse_answer(raw) -> Answer \| None` | AC5, AC6, AC11 |
| P5 Ollama client | `backend/evaluation/ollama.py` | `OllamaReader(base_url, client=None)`: `check(models) -> list[str]` (problems), `warm_up(model)`, `read(model, prompt, image=None) -> RawAnswer(text, error)`; `Reader` protocol | AC5, AC6, AC10, AC12, AC19 |
| P6 Scoring | `backend/evaluation/scoring.py` | `score_receipt(truth, answer, seconds) -> Score`; `score_lines(truth_lines, answer_lines) -> (f1, name_similarity)`; `aggregate(scores) -> Row`; `meets_criteria(row)`; criteria constants | AC11, AC13–AC17 |
| P7 Runner and report | `backend/evaluation/runner.py`, `report.py` | `run_evaluation(folder, variants, ocr, reader, clock, out) -> list[Row]`: per variant, warm up, then each receipt, write the detail file, print progress; `render_summary(rows, skipped) -> str` | AC3, AC5–AC7, AC11, AC12, AC17, AC18 |
| P8 CLI | `backend/evaluation/__main__.py`, `cli.py` | `main(argv, deps=None) -> int` with `argparse`: `init`, `run --variant … [--limit N] [--subset full] [--dir PATH]`; exit codes 0, 1 (Ollama), 2 (input), 3 (unexpected error, AC21) | AC1–AC4, AC7–AC10 |
| P9 Runtime | `compose.yaml`, `.env.example`, `backend/pyproject.toml`, `backend/uv.lock` | Service `eval`; `RRMC_EVAL_DIR`; Pillow; pyright includes `evaluation`; pytest marker `tesseract` | PC8, AC20 |

### Data flow of `run`

1. Parse the variants (AC8, AC9), then load every truth file (AC2) and collect the receipts
   in name order (AC3, AC4). Nothing is sent to Ollama before these checks pass.
2. `reader.check(models)`: `GET /api/tags`; any problem prints the AC10 message, exit 1.
3. Write `results/<run id>/receipts.json`, the index → file name map, for the user only.
4. For each variant in the given order: `warm_up(model)` (an untimed request that loads the
   model, as the app does at start, FR-30), then for each selected receipt:
   start the clock; for `ocr:` preprocess and OCR, then `read` with the text prompt; for
   `vision:` `read` with the image prompt and the original image; stop the clock; parse and
   score; write `<variant folder>/<index>.json`; print progress.
5. Aggregate per variant, print the summary and write `summary.md`.

Variants run one after another, so each model is loaded once.

### Ollama request

`POST /api/generate` with `{"model", "prompt", "format": ANSWER_SCHEMA, "stream": false,
"options": {"temperature": 0, "num_ctx": 8192}, "keep_alive": "10m"}` and, for `vision:`,
`"images": [<base64>]`. `num_ctx` is set because Ollama's default context (2048–4096 tokens)
can cut a long receipt's OCR text silently. The timeout is 600 s (AC12). The detail file also
keeps Ollama's `prompt_eval_count`, `eval_count` and durations, to explain slow receipts.

### Scoring rules

- `store`: `normalize_key` from @backend/app/categorization/names.py on both names; true when
  equal or one contains the other.
- `amounts`: multisets of `amount_cents` and `a`; matched = size of the multiset
  intersection; precision = matched / answer lines, recall = matched / truth lines, F1 =
  2PR / (P + R), 0 when nothing matches.
- `names`: truth and answer lines are paired by equal amount, in the order they appear; the
  similarity is `difflib.SequenceMatcher(None, a, b).ratio()` on normalized names; a receipt
  with no pairs has no value and is left out of the mean.
- Percentiles: nearest rank. Percentages: of all receipts for `valid` and `in_time`, of valid
  receipts for the others (as in the Metrics table), and 0 % when there are none.
- An unfilled template is detected by comparing the loaded JSON with `TEMPLATE`.
- Truth file errors name the file and field only, never the value: `must be an integer`,
  `must be a date YYYY-MM-DD`, `is required`, `must not be empty`.

### Runtime

```yaml
  eval:
    profiles: [eval]
    build: ./backend
    env_file:
      - path: ${RRMC_ENV_FILE:-.env}
        required: true
    volumes:
      - ./backend:/app
      - ${RRMC_EVAL_DIR:-./source/eval}:/data/eval
    extra_hosts:
      - "host.docker.internal:host-gateway"
```

Inside the container the folder is always `/data/eval`; `--dir` overrides it in tests. The
Ollama address comes from `load_settings().ollama_url`. No ports are published.

Pillow is added to `backend/pyproject.toml` and the lock file is updated with the documented
`uv lock` command. It is the standard Python imaging library, has no system dependencies in
the slim image, and the receipt-reading spec needs image preprocessing too (FR-6). Its
bundled default font draws the synthetic test images.

The Tesseract integration test is marked `tesseract` and left out of the default run
(`addopts = "-m 'not tesseract'"`), as the `tdd` skill asks for tests that need a real
engine; it runs with `docker compose run --rm backend pytest -m tesseract`.

### Testing approach

- Unit tests in `backend/tests/evaluation/` use `tmp_path`, fake `Ocr` and `Reader`
  classes, a fake clock, and `httpx2.MockTransport` for `OllamaReader`.
- The CLI is tested through `main(argv, deps)` with fakes and `capsys`; exit codes and
  output are checked as in the ACs.
- AC18 uses the marker `SECRET-CONTENT` in file names, truth values, OCR text and answers,
  and checks stdout and `summary.md`.
- AC20 is a check in `scripts/container-tests.ps1`, next to the existing ignore checks.
- Coverage: `pytest --cov=evaluation --cov-branch`.

### Decisions

- No ADR for the tool. The result of the evaluation will be an ADR ("Receipt reading
  model"), written by the user's choice with the aggregate numbers only.
- Tesseract `--psm 4` (one column of text of varying sizes) fits receipts; the receipt-reading
  spec may change it with evidence from this tool.

### Files to Modify (refined)

Adds to the table above: `backend/evaluation/__init__.py`, `__main__.py`, `cli.py`,
`truth.py`, `variants.py`, `ocr.py`, `prompt.py`, `ollama.py`, `scoring.py`, `runner.py`,
`report.py`; `backend/tests/evaluation/` with one test file per module
(`test_eval_truth.py`, … — basenames must be unique).

### AC coverage

| AC | Parts |
|---|---|
| AC1–AC4 | P1, P8 |
| AC5, AC6 | P3, P4, P5, P7 |
| AC7–AC9 | P2, P8 |
| AC10 | P5, P8 |
| AC11, AC12 | P4, P5, P7 |
| AC13–AC17 | P6, P7 |
| AC18 | P7 |
| AC19 | P5 |
| AC20 | P9 |

## Changes during implementation

- **AC12** also covers OCR failures: an image that cannot be opened or preprocessed, or a
  Tesseract failure, records `"error": "ocr_error"` and the run goes on (approved by the
  user, 2026-10-28).
- **Store score:** an empty answer store never matches, although an empty string is
  "contained" in every name.
- **Folder check:** a missing evaluation folder prints `Evaluation folder not found: <path>`
  and exits with code 2. A missing `--variant`, `--limit` or `--subset` before any
  `--variant`, a limit below 1 or another subset value are argparse errors (code 2).
- **Truth file messages** beyond AC2 (all without the value): `must not be negative`,
  `must be text`, `must be a list`, `is not a known field`, `must be a JSON object`,
  `not valid JSON`, `cannot be read`; line fields are named like `lines[0].amount_cents`.
- **Test helpers** live in `backend/tests/evaluation/eval_fakes.py`.
- **Docs:** also `docs/glossary.md`, `docs/learnings.md` and the `AGENTS.md` layout.
- Coverage of `backend/evaluation/`: 98 % lines with branches (`__main__.py` is the only
  uncovered module, three lines).

## Tasks

Plan approved: 2026-10-28. Each task follows Red → Green → Refactor (`.agents/skills/tdd/SKILL.md`)
and ends with the backend tests, lint, format and type checks passing. Test names start with
the AC IDs they prove. Tests live in `backend/tests/evaluation/` with unique basenames
(`test_eval_*.py`) and use synthetic data only.

### Setup

- [x] **T1 Package and dependency** (PC8). Add `pillow` to `backend/pyproject.toml`, update
  `uv.lock` with the documented `uv lock` command, rebuild the backend image; add
  `evaluation` to pyright's `include`; register the pytest marker `tesseract` and exclude it
  by default; create `backend/evaluation/__init__.py`. Proof: `pytest`, `pyright` and
  `ruff` pass; `python -c "import PIL"` works in the container.

### Inputs

- [x] **T2 Truth templates** (AC1). `truth.py`: `TEMPLATE`, `init_templates`. Proof:
  `test_eval_truth.py` — a template is created only for an image without a truth file, and
  the count is returned.
- [x] **T3 Truth loading** (AC2, AC4). `Truth`, `TruthLine`, `load_truth`,
  `TruthFileError`. Proof: valid files load; each invalid field gives its message without
  the value; an unfilled template is reported as unfilled.
- [x] **T4 Receipt collection** (AC3, AC4). `collect_receipts` in name order, counting images
  without a truth file and unfilled templates as skipped. Proof: `test_eval_truth.py`.
- [x] **T5 Variants and selection** (AC7–AC9). `variants.py`: `parse_variant`,
  `VariantError`, cloud refusal, `select_receipts` (`--limit`, `--subset full`),
  `folder_name`. Proof: `test_eval_variants.py`.

### Reading

- [x] **T6 Prompt and answer** (AC5, AC6, AC11). `prompt.py`: `ANSWER_SCHEMA`,
  `INSTRUCTIONS`, `text_prompt`, `image_prompt`, `Answer`, `parse_answer`. Proof:
  `test_eval_prompt.py` — the OCR text is in the text prompt; invalid JSON or a wrong shape
  gives `None`.
- [x] **T7 Preprocessing and OCR** (AC5). `ocr.py`: `preprocess` (grayscale, ≥ 1 500 px
  wide, autocontrast), `TesseractOcr`. Proof: `test_eval_ocr.py` for `preprocess` with a
  Pillow image; `test_eval_tesseract.py` (marker `tesseract`) reads a drawn synthetic receipt.
- [x] **T8 Ollama client** (AC5, AC6, AC10, AC12, AC19). `ollama.py`: `OllamaReader.check`,
  `warm_up`, `read` (request body as in the Plan, image as base64, timeout 600 s, errors as
  `model_error`). Proof: `test_eval_ollama.py` with `httpx2.MockTransport`, including that
  every request goes to the configured base URL only.

### Scoring and run

- [x] **T9 Receipt scoring** (AC11, AC13–AC16). `scoring.py`: `score_receipt`,
  `score_lines`. Proof: `test_eval_scoring.py`.
- [x] **T10 Aggregates and criteria** (AC17). `aggregate`, percentiles, `meets_criteria`.
  Proof: `test_eval_scoring.py`.
- [x] **T11 Runner** (AC5–AC7, AC11, AC12). `runner.py`: run order, warm-up, timing with an
  injected clock, detail files per variant folder, `receipts.json`, progress lines. Proof:
  `test_eval_runner.py` with fake `Ocr` and `Reader`.
- [x] **T12 Report** (AC17, AC18). `report.py`: printed table and `summary.md`. Proof:
  `test_eval_report.py`, including the `SECRET-CONTENT` marker check across stdout and
  `summary.md`.

### Command line and runtime

- [x] **T13 CLI** (AC1–AC4, AC7–AC10). `cli.py`, `__main__.py`: `init`, `run`, options,
  exit codes 0/1/2/3, messages as in the ACs. Proof: `test_eval_cli.py` through
  `main(argv, deps)` and `capsys`.
- [x] **T14 Compose service and setting** (PC8, AC20). Service `eval` in `compose.yaml`,
  `RRMC_EVAL_DIR=./source/eval` in `.env.example`, the ignore check in
  `scripts/container-tests.ps1`. Proof: `docker compose --profile eval config` is valid;
  container tests pass; `docker compose --profile eval run --rm eval python -m evaluation
  init` runs against an empty folder.
- [x] **T15 Documentation**. `docs/development.md` (how to run the evaluation, privacy
  rules, `pytest -m tesseract`), `docs/architecture.md` (the tool outside `app/`),
  `docs/content-plan.md`, `specs/README.md`; keep the AGENTS.md command table in sync if a
  command is added. Proof: commands in the docs were run; links resolve.
- [x] **T16 Full check**. All backend checks, `pytest -m tesseract`, coverage of
  `evaluation` ≥ 90 %, container tests. Frontend is unchanged, so its checks are not needed.

## Audit

Audited 2026-10-28, verdict PASS after one fix cycle. An independent reviewer read the code
against this spec; its findings were checked in the code before acting on them.

- Acceptance criteria: 21/21 met; every AC has a test whose name carries its ID (AC20 in
  `scripts/container-tests.ps1`).
- Tests: backend 460 passed, `pytest -m tesseract` 1 passed; coverage of
  `backend/evaluation/` 98 % with branches (scoring, variants and runner 100 %). Container
  tests passed. Lint, format and type checks clean. Frontend unchanged.
- Security: three findings, fixed (see [learnings](../../docs/learnings.md)): an unreadable
  `vision:` image or any unexpected error printed a traceback that could hold a file name
  (now `image_error`, and AC21 with exit code 3); proxy variables could route requests to
  another host (`trust_env=False`); the criteria compared rounded percentages. Also fixed:
  a repeated variant failed only after the first variant had run (AC9); a lone surrogate in
  an answer could stop the detail write; an image too large for Pillow is now `ocr_error`;
  the AC18 test uses the spec's marker `SECRET-CONTENT`; `python -m evaluation` is tested
  end to end. `pip-audit` is not installed in the backend image and was not run.
- Later: phone photos are not turned upright from their EXIF orientation before OCR; check
  this after the first real run (done: see below). An invalid answer gets `names` 0.0, while a valid answer
  with no amount match is left out of the `names` mean, as the Metrics table says.

## Change: Image orientation (2026-10-29)

- **Why:** the first real run (25 phone photos) gave every `ocr:` variant 0 % `total` and
  `date`, while `vision:qwen2.5vl:7b` had 100 % `total` on five receipts. All 25 photos carry
  EXIF orientation 6, and `preprocess` dropped the tag, so Tesseract read the receipts on
  their side: nine OCR texts were empty and most others had only a few digits. Checked from
  image metadata and OCR text lengths only.
- **Changes:** PC4 (EXIF turn and OSD; EXIF turn for `vision:`), PC7 (`orientation` in
  detail files), AC22–AC26, test rows, a Risk entry. AC5's OCR now gets the image after OSD;
  the other ACs are unchanged.
- **Status:** spec change approved by the user 2026-10-29; Plan and Tasks approved the same day.

### Plan

| Part | File | Contents | ACs |
|---|---|---|---|
| O1 EXIF | `backend/evaluation/ocr.py` | `exif_orientation(image) -> int \| None` (tag `0x0112`); `preprocess` calls `ImageOps.exif_transpose` before grayscale; `upright_original(image) -> bytes` returns the original bytes for no tag or tag 1, otherwise the turned image in its own format (JPEG quality 95, PNG) | AC22, AC23, AC26 |
| O2 OSD | `backend/evaluation/ocr.py` | `Oriented(image, osd_rotation, osd_confidence)`; `Ocr.orient(image) -> Oriented` next to `read`; `TesseractOcr.orient` runs `tesseract stdin stdout --psm 0`, reads `Rotate:` and `Orientation confidence:`, and turns the image clockwise by `Rotate` degrees (Pillow `rotate(-rotation, expand=True)`, saved as PNG) when the rotation is 90, 180 or 270 and the confidence ≥ `OSD_MIN_CONFIDENCE` (2.0); an exception, a non-zero exit or missing values give `Oriented(image, 0, None)` | AC24, AC25 |
| O3 Runner | `backend/evaluation/runner.py` | `ocr:` path: `exif_orientation`, `preprocess`, `ocr.orient`, `ocr.read(oriented.image)`; `vision:` path: `upright_original`, an unreadable image is `image_error`; `orientation` in the detail file | AC22–AC26 |

`read` keeps its signature, so OCR and its tests stay as they are; `orient` is a separate
step that the runner calls. The direction of `Rotate` was checked with the real Tesseract on
synthetic images: an image turned 90 degrees counterclockwise reports `Rotate: 90`, and
turning it 90 degrees clockwise puts it upright.

### Tasks

Each task follows Red → Green → Refactor and ends with backend tests, lint, format and type
checks passing.

- [x] **T17 EXIF in preprocessing** (AC22, AC23). `exif_orientation`, `exif_transpose` in
  `preprocess`. Proof: `test_eval_ocr.py` — PNGs with tags 3, 6, 8 equal the preprocessed
  upright image; no tag gives `None` and the old result.
- [x] **T18 OSD** (AC24, AC25). `Oriented`, `Ocr.orient`, `TesseractOcr.orient`,
  `OSD_MIN_CONFIDENCE`. Proof: `test_eval_ocr.py` with `FakeRun` for 90/180/270 at 5.0,
  1.5, 0, exit code 1, output without values, and an exception; `test_eval_tesseract.py`
  (marker `tesseract`) for the 20-line receipt turned 90 degrees.
- [x] **T19 Vision image** (AC26). `upright_original`. Proof: `test_eval_ocr.py` — JPEG with
  tag 6 comes back upright without the tag; without the tag the bytes are unchanged.
- [x] **T20 Runner** (AC22–AC26). Detail file `orientation`; `FakeOcr.orient` in
  `eval_fakes.py`. Proof: `test_eval_runner.py`.
- [x] **T21 Documentation and check.** `docs/development.md`, `docs/learnings.md`,
  `specs/README.md`; all backend checks, `pytest -m tesseract`, coverage of `evaluation`
  ≥ 90 %. Then the user reruns the evaluation.

### Files to Modify

| File | Change |
|---|---|
| `backend/evaluation/ocr.py` | `exif_orientation`; EXIF turn in `preprocess`; `upright_original`; `Oriented`, `Ocr.orient` and `TesseractOcr.orient` with `OSD_MIN_CONFIDENCE` |
| `backend/evaluation/runner.py` | `ocr:` path through `orient`; `vision:` path through `upright_original` (unreadable image: `image_error`); `orientation` in detail files |
| `backend/tests/evaluation/test_eval_ocr.py`, `test_eval_tesseract.py`, `test_eval_runner.py`, `eval_fakes.py` | Tests for AC22–AC26 |
| `docs/development.md` | Model evaluation: images are turned upright (EXIF, then OSD); `orientation` in detail files |
| `docs/learnings.md` | Entry: phone photos read on their side |
| `specs/README.md` | Status of this spec |
| `docs/content-plan.md` | Note that the orientation change is audited and that receipt reading needs it too |

### Audit

Audited 2026-10-29, verdict PASS after one fix cycle. An independent reviewer read the code
against this change; its findings were checked in the container before acting on them.

- Acceptance criteria: AC22–AC26 met, each with tests whose names carry the AC ID; the
  earlier AC1–AC21 are unchanged and their tests pass.
- Tests: backend 500 passed, `pytest -m tesseract` 2 passed; coverage of
  `backend/evaluation/` 98 % with branches (`ocr.py` 99 %, the uncovered line is the
  subprocess call; `runner.py` 100 %). Lint, format and type checks clean. Frontend
  unchanged.
- Fixed from the review:
  - an MPO file (Ultra HDR phone photo) with an EXIF turn was sent to a `vision:` model as
    PNG; it is now JPEG;
  - the color profile was dropped when a `vision:` image was turned; it is now kept;
  - an EXIF value outside 1–8 was recorded and made `upright_original` re-encode the image;
    it now counts as no tag (PC4 says so);
  - an OSD confidence of NaN would have turned the image and written invalid JSON; it now
    counts as failed OSD;
  - tests now check that the top of the image is up (a constant extra turn would have
    passed before) and the confidence limit 2.0 itself;
  - test rows and Files to Modify named `TesseractOcr.read` instead of `orient`.
- Not reproduced: the reviewer expected broken EXIF data to stop the run. Pillow 13 skips
  it in ten synthetic cases (garbage, short and truncated headers, bad offsets and counts,
  wrong tag types); a regression test keeps it so (`test_ac23_broken_exif_counts_as_no_tag`).
- Security: no new output to the screen or `summary.md`; detail files gain only numbers.
  Pillow's warning `Corrupt EXIF data` goes to stderr without file names or content.
  `pip-audit` is not installed in the backend image and was not run; no dependency changed.
