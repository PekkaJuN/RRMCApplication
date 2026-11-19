# RRMCApplication

Receipt Reader Mapper Calculator: a local app that turns photos of shopping receipts into
categorized spending.

Copy receipt images into the import folder and start an import. The app reads each receipt
with local OCR (Tesseract) and a local language model (Ollama), splits it into line items and
puts each line into a category. You check and correct the result in a Finnish-language UI,
with the receipt image beside an editable table. The app remembers your corrections and shows
spending per category and group for each ISO week and month. It also has monthly budgets,
CSV and PDF export, and a yearly archive.

Everything runs on your own computer. Receipt images, OCR text, model calls and the database
never leave it.

## Stack

Python and FastAPI backend, React, Vite and TypeScript frontend, SQLite storage, all run with
Docker Compose. Ollama runs on Windows.

## Documentation

- [Project description](docs/projectdescription.md): purpose, users and features
- [Development guide](docs/development.md): setup and commands
- [Architecture](docs/architecture.md): components and data flow
- [Docs index](docs/README.md) and [feature specs](specs/README.md)
