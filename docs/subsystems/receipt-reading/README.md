# Receipt Reading

Navigation: ↑ [Architecture](../../architecture.md) | → [Storage](../storage/README.md) | → [UI](../ui/README.md)

## Overview

Receipt reading will turn a receipt image into a validated structured receipt: preprocess
the image, run OCR, and parse the text with the local model (FR-6–FR-10). That work comes
with the receipt-reading spec.

Today it has only the engine interfaces, `OcrEngine` and `ReceiptModel`, with their
availability checks, real implementations and deterministic fakes. They live in the shared
`engines` package, which categorization will also use.

## Key Files and Entry Points

- @backend/app/engines/ocr.py — `OcrEngine`, `TesseractOcrEngine`, `FakeOcrEngine`
- @backend/app/engines/model.py — `ReceiptModel`, `OllamaReceiptModel`, `FakeReceiptModel`,
  `ModelLoadError`
- @backend/app/engines/factory.py — `create_engines(settings)` returns the real pair or the
  fakes

## Interfaces

Both interfaces are `typing.Protocol`s; code depends on the protocol only.

| Method | Real implementation | Fake |
|---|---|---|
| `OcrEngine.check()` → `ok` / `unavailable` | Runs `tesseract --list-langs` (5 s timeout); `ok` when `fin` and `eng` are listed | `ok`; never starts a process |
| `ReceiptModel.check()` → `ok` / `unavailable` / `missing_model` | `GET /api/tags` on Ollama (2 s timeout); `missing_model` when `RRMC_MODEL` is not listed; `name:latest` matches `name` | `ok`; no HTTP |
| `ReceiptModel.load()` | `POST /api/generate` with `{"model": RRMC_MODEL, "keep_alive": -1}`, which keeps the model in memory; raises `ModelLoadError` on failure | does nothing |

`RRMC_ENGINES` chooses the implementation: `real` (default) or `fake`. Tests and E2E runs use
the fakes, so they need neither Tesseract nor Ollama. Reading and parsing methods are added
to these interfaces by the receipt-reading spec.

## Data Flow

Today only [health](../../api-reference.md#get-apihealth) calls the engines: `check()` on
every health request, and `load()` through `ModelLoader` (@backend/app/health/service.py)
at start and on the first health check that finds the model available.

## Dependencies

- Uses: Tesseract in the backend container; Ollama on Windows at `RRMC_OLLAMA_URL`, through
  `httpx2`.
- Used by: health; later import and categorization.

## Modules

None yet.

## Known Issues and Gotchas

- The 2 second timeout of `ReceiptModel.check()` keeps the health answer under 3 seconds
  when Ollama does not answer. Loading a model uses a 300 second timeout and runs in a
  background thread.
- `httpx2` logs each Ollama request at `INFO` (URL and status, no content), so a running UI
  adds one log line every 30 seconds.

## Related Documents

- [architecture.md](../../architecture.md#key-interfaces): where the interfaces sit
- [Foundation spec](../../../specs/features/foundation.md) PC6 and PC7
