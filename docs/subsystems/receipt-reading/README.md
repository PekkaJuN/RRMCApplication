# Receipt Reading

Navigation: ↑ [Architecture](../../architecture.md) | → [Import](../import/README.md) | → [Storage](../storage/README.md) | → [UI](../ui/README.md)

## Overview

Receipt reading turns one receipt image into a **read receipt**: store name, purchase date,
total in integer cents, the item lines, and the raw OCR text (PRD FR-6–FR-10). Import calls
it for every new image, between the duplicate check and the commit. Reading never writes to
the database and never chooses categories.

The app reads on the **OCR path**: the image is turned upright and preprocessed, Tesseract
reads the text, and the local text model turns the text into JSON, which is then checked
([ADR 0003](../../adr/0003-receipt-reading-model.md)). Everything sits behind one interface,
the **receipt reader**, so a vision reader can be added later without changing import.

The behavior is specified in the
[receipt-reading spec](../../../specs/features/receipt-reading.md).

## Key Files and Entry Points

- @backend/app/receipt_reading/reader.py — `ReceiptReader` (the interface) and
  `OcrReceiptReader`
- @backend/app/receipt_reading/preprocess.py — `preprocess`, `exif_orientation`,
  `UnreadableImageError`
- @backend/app/receipt_reading/prompt.py — `INSTRUCTIONS` (the Finnish receipt rules of
  FR-9), `ANSWER_SCHEMA`, `text_prompt`, `parse_answer`
- @backend/app/receipt_reading/validation.py — `to_read_receipt`: the rules on top of the
  schema
- @backend/app/receipt_reading/receipt.py — `ReadReceipt`, `ReadLine`, `ReadFailedError`
- @backend/app/receipt_reading/fake.py — `FakeReceiptReader`, `FAKE_RECEIPT`,
  `FAKE_PARSE_FAILED_IMAGE`
- @backend/app/receipt_reading/factory.py — `create_reader(settings, engines)`
- @backend/app/engines/ocr.py — `OcrEngine`, `TesseractOcrEngine`, `FakeOcrEngine`
- @backend/app/engines/model.py — `LoadableModel`, `ReceiptModel`, `OllamaReceiptModel`,
  `FakeReceiptModel`, `is_cloud_model` and the model errors
- @backend/app/engines/factory.py — `create_engines(settings)` returns the real pair or the
  fakes

The evaluation tool (@backend/evaluation/) imports the preprocessing, the Tesseract engine,
the prompt, the schema and `parse_answer` from here, so it measures what the app ships. It
does not use `to_read_receipt`, whose extra rules would change its `valid` metric.

## Interfaces

`ReceiptReader.read(image: bytes) -> ReadReceipt` raises:

- `ReadFailedError(reason)` when this image cannot be read; the next one may be. `reason` is
  the import failure reason: `unreadable_image`, `ocr_failed`, `no_text` or `parse_failed`.
- `ModelUnavailableError` when the model cannot be used for any image; import stops the run
  (FR-31).

The engines are `typing.Protocol`s; code depends on the protocol only.

| Method | Real implementation | Fake |
|---|---|---|
| `OcrEngine.check()` → `ok` / `unavailable` | Runs `tesseract --list-langs` (5 s timeout); `ok` when `fin` and `eng` are listed | `ok` |
| `OcrEngine.orient(image)` → `Oriented` | `tesseract stdin stdout --psm 0`; turns the image by `Rotate` (90, 180, 270) when the orientation confidence is at least 2.0; any failure keeps the image | image unchanged |
| `OcrEngine.read(image)` → text | `tesseract stdin stdout -l fin+eng --psm 4` (120 s timeout); an error exit, a missing binary or a timeout raises `OcrError` | fixed text |
| `ReceiptModel.check()` → `ok` / `unavailable` / `missing_model` | `GET /api/tags` (2 s timeout); `name:latest` matches `name` | `ok` |
| `ReceiptModel.load()` | `POST /api/generate` with `keep_alive: -1`; raises `ModelLoadError` | nothing |
| `ReceiptModel.generate(prompt, schema)` → raw text | `POST /api/generate`, see [Model request](#model-request) | a fixed valid answer |

`RRMC_ENGINES` chooses the implementation: `real` (default) or `fake`. With `fake`,
`create_reader` returns `FakeReceiptReader`, which never calls the engines: it returns
`FAKE_RECEIPT` for every image, except images whose SHA-256 is in its table
(`FAKE_PARSE_FAILED_IMAGE` fails with `parse_failed`). E2E tests use that to show a failure.

Health uses only `LoadableModel` (`check` and `load`), the part of `ReceiptModel` it needs.

## Data Flow

`OcrReceiptReader.read`:

| Step | On error | Reason |
|---|---|---|
| 1. `preprocess`: upright from EXIF (tags 1–8; others count as none), grayscale, upscale to at least 1 500 px wide, automatic contrast; PNG | not decodable by Pillow | `unreadable_image` |
| 2. `orient`, then `read` with Tesseract | `OcrError` | `ocr_failed` |
| 3. Text is empty after trimming; the model is not called | — | `no_text` |
| 4. `generate(text_prompt(text), ANSWER_SCHEMA)` | `ModelTimeoutError`, `ModelAnswerError` | `parse_failed` |
| | `ModelUnavailableError` | passes through; import stops |
| 5. `parse_answer`: strict JSON schema | `None` | `parse_failed` |
| 6. `to_read_receipt`: the rules below | broken rule | `parse_failed` |

The answer uses short keys to keep output tokens few, which are the slowest part on the
CPU: `{"s": store, "d": "YYYY-MM-DD", "t": total cents, "l": [{"n": name, "a": amount cents,
"r": deposit refund}]}`.

Rules of `to_read_receipt`:

| Field | Rule |
|---|---|
| `s` | Trimmed; empty is kept as `""` |
| `d` | A real date in ASCII `YYYY-MM-DD` is kept; anything else becomes no date (`None`), for the user to fix |
| `t` | Below 0 or above 2^63 − 1 fails |
| `l` | No lines fails; a blank name fails; an amount outside −2^63 … 2^63 − 1 fails; `r` with an amount ≥ 0 fails; names are trimmed |

The integer range is SQLite's. Checking it here makes such an answer `parse_failed`; without
the check, saving it would raise `OverflowError` and fail the image as `internal_error`.

A total that differs from the sum of the lines is not a reading failure; the review UI warns
about it (FR-20). The OCR text is kept as Tesseract returned it (FR-10).

### Model request

```json
{"model": "<RRMC_MODEL>", "prompt": "...", "format": {"...": "ANSWER_SCHEMA"}, "stream": false,
 "options": {"temperature": 0, "num_ctx": 8192}, "keep_alive": -1}
```

| Outcome | Error |
|---|---|
| Connection refused, connect timeout, connection lost | `ModelUnavailableError` |
| HTTP 404 (model not pulled) | `ModelUnavailableError` |
| Read, write or pool timeout (300 s) | `ModelTimeoutError` |
| Any other error status; a body without `response` | `ModelAnswerError` |
| `RRMC_MODEL` ends in `-cloud` or `:cloud` | `ModelUnavailableError`, no request |

## Dependencies

- Uses: Tesseract in the backend container; Ollama on Windows at `RRMC_OLLAMA_URL`, through
  `httpx2`; Pillow.
- Used by: [import](../import/README.md) (the reader), health (`check()` and `load()`), the
  evaluation tool (preprocessing, Tesseract, prompt, schema); later categorization
  (`generate()`).

## Modules

None yet.

## Known Issues and Gotchas

- **Phone photos are stored on their side** with the turn in the EXIF orientation tag.
  Dropping the tag before OCR made Tesseract read every photo sideways
  ([learnings](../../learnings.md)). Synthetic test images include EXIF-tagged photos.
- **OSD needs text.** With fewer than about 20 lines its confidence stays under 2.0 and the
  image is left as it is; that is not an error.
- **No proxy.** The Ollama client is built with `trust_env=False`, so proxy variables can
  never route OCR text to another host (NFR-1).
- **Nothing of the receipt in errors.** Exception messages name no prompt, answer, store or
  product; import logs only counts (NFR-3).
- The 2 second timeout of `ReceiptModel.check()` keeps the health answer under 3 seconds
  when Ollama does not answer. Loading a model uses a 300 second timeout and runs in a
  background thread.
- `httpx2` logs each Ollama request at `INFO` (URL and status, no content), so a running UI
  adds one log line every 30 seconds.
- Real Tesseract tests are marked `tesseract` and run with `pytest -m tesseract`.

## Related Documents

- [Receipt-reading spec](../../../specs/features/receipt-reading.md)
- [ADR 0003](../../adr/0003-receipt-reading-model.md): why the OCR path and this model
- [architecture.md](../../architecture.md#key-interfaces): where the interfaces sit
- [datamodel.md](../../datamodel.md#receipts): where the read data is stored
- [Model evaluation spec](../../../specs/features/model-evaluation.md) PC4: the reading steps
  this subsystem took over
