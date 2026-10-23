# 0001. Technology stack

- Status: accepted
- Date: 2026-10-22

## Context

RRMCApplication reads photos of personal shopping receipts, categorizes the lines and totals
them per week and month. Receipts are personal financial data, so all processing must stay on
the user's Windows computer (PRD NFR-1). The app has one user, runs locally and needs a UI
where the receipt image and an editable table are side by side. Finnish receipts must be read
reliably, and categorization must improve from the user's corrections. The stack was decided
before any code was written; it is listed in [PRD section 8](../../specs/PRD.md#8-solution-outline-decided).

## Decision

| Area | Choice |
|---|---|
| OCR | Tesseract 5.x with the `fin` and `eng` language packs |
| Parsing and categorization | A local model through Ollama, with schema-validated JSON output. The model name is one setting (7–9B class first, 14B as an option). |
| Backend | Python + FastAPI, listening on `127.0.0.1` only |
| Frontend | React + Vite + TypeScript |
| Storage | SQLite, one file outside version control |
| Export | CSV first; Google Sheets (gspread) later, behind one exporter interface |
| Testing | pytest; Vitest, React Testing Library and MSW; Playwright |

## Consequences

- No receipt data leaves the computer: OCR, the model and the database are all local, and no
  cloud OCR or cloud model is used.
- The user must install Python, Node.js, Tesseract and Ollama; setup is documented in
  `docs/development.md`.
- Model quality and speed depend on the user's hardware. Because the model name is a setting
  and the model sits behind an interface, it can be changed without code changes.
- Tesseract and Ollama are slow and non-deterministic in tests, so both sit behind interfaces
  with deterministic fakes (PRD NFR-13).
- SQLite fits one local user; it is not designed for concurrent multi-user access.
- Whether parsing uses a text model on OCR output or a vision model on the image is still open
  (PRD open question 4). Choosing a vision model would be recorded in a new ADR.
- Two languages (Python and TypeScript) and two test toolchains are maintained.
