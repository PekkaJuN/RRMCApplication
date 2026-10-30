# 0003. Receipt reading: OCR with a mixture-of-experts text model

- Status: accepted
- Date: 2026-10-30

## Context

[ADR 0001](0001-tech-stack.md) chose Tesseract for OCR and a local Ollama model for
parsing, and left open whether a vision model reading the image would be better (PRD open
question 4). The [model evaluation](../../specs/features/model-evaluation.md) compared the
two paths on 25 of the user's receipts on the user's computer (CPU only, no GPU; PRD open
question 1). The decision criteria were `valid` 100 %, `total` ≥ 90 %, `date` ≥ 95 % and
`in_time` (≤ 180 s, NFR-8) ≥ 90 %.

| Variant (25 receipts) | `valid` | `total` | `date` | `store` | Median s | p90 s | Max s | `in_time` |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `ocr:qwen2.5:7b` | 100 % | 52 % | 56 % | 48 % | 23 | 80 | 186 | 96 % |
| `ocr:qwen3:30b-a3b-instruct-2507-q4_K_M` | 100 % | 60 % | 60 % | 60 % | 18 | 74 | 188 | 96 % |
| `ocr:gemma3:12b` | 100 % | 60 % | 52 % | 64 % | 42 | 112 | 371 | 92 % |
| `vision:qwen2.5vl:7b` | 100 % | 100 % | 84 % | 72 % | 176 | 286 | 344 | 56 % |

No variant met the criteria. The vision model was more accurate but too slow on this
computer: almost half of the receipts took longer than 3 minutes. Among the OCR variants,
the qwen3 model was the fastest and as accurate as or more accurate than the others, except
for the store name.

## Decision

- Receipts are read on the **OCR path**: Tesseract (`fin+eng`), then the text model
  `qwen3:30b-a3b-instruct-2507-q4_K_M`. This exact tag is the default of `RRMC_MODEL`; the
  plain tag `qwen3:30b-a3b` may name another build.
- The model is a mixture-of-experts model with 30 B parameters, of which about 3 B are
  active per token, so on the CPU it answers as fast as a 7 B model. This replaces the
  "7–9B class" default of PRD FR-29.
- Reading sits behind one interface, the receipt reader (image in, read receipt out), so a
  vision reader can be added later without changing import
  ([receipt-reading spec](../../specs/features/receipt-reading.md)).

## Consequences

- Reading is fast (median 18 s; 96 % of receipts within NFR-8), but totals and dates are often wrong, so the review UI
  (FR-16–FR-20) is what makes the data right. A date the model gets wrong in format is
  stored empty rather than failing the image.
- Switching to a vision reader needs a new ADR, because this ADR and ADR 0001 name
  Tesseract. Re-running the evaluation tool on new receipts or models shows when that is
  worth it; the tool uses the app's reading code, so it measures what the app ships.
- The slowest OCR receipt took 188 s, so the model time limit per receipt is set above the
  NFR-8 target (300 s in the receipt-reading spec).
- A 30 B model needs much more memory than a 7 B one while Ollama keeps it loaded (FR-30);
  the computer has 64 GB.
