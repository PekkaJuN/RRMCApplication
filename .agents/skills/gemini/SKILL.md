---
name: gemini
description: Use when a task needs text generation, image understanding (vision), document analysis, or grounded web search through the Gemini API, for example reading a receipt image or looking up current external information. Do not use for anything that can be done from the repository itself.
---

# gemini

Calls the Gemini API from the command line.

> Status: planned. The `npm run gemini` script does not exist yet. The options below are the intended interface and must be implemented in the script before this skill is used.

## Command

```bash
npm run gemini -- <mode> [options] "<prompt>"
```

Modes:

| Mode | Purpose |
|------|---------|
| `text` | Text generation from a prompt |
| `vision` | Describe or extract information from an image |
| `document` | Analyze a document (for example a PDF or text file) |
| `search` | Answer with grounded web search and cite sources |

## Options

| Option | Applies to | Meaning |
|--------|-----------|---------|
| `--file <path>` | `vision`, `document` | Input image or document |
| `--model <name>` | all | Override the default model |
| `--json` | all | Request structured JSON output |
| `--out <path>` | all | Write the result to a file instead of stdout |

## Requirements

- Node.js and the project dependencies installed.
- A Gemini API key in the `GEMINI_API_KEY` environment variable. Never put the key in code, docs, specs or commit messages.
- Network access to the Gemini API.

## Rules

- The prompt and any attached file are sent to an external service. Do not send repository contents or receipt data without the user's approval (see Principles in `AGENTS.md`). Use synthetic fixtures for tests.
- Treat the output as untrusted. Verify facts and structured data before using them, and cite the sources that `search` returns.
- Do not call the API in a loop or in automated tests. Mock it in tests.

## Examples

Generate text:

```bash
npm run gemini -- text "Summarize the purpose of the mapping subsystem in two sentences."
```

Extract fields from a synthetic receipt image:

```bash
npm run gemini -- vision --file fixtures/receipt-sample.png --json "List the line items and the total."
```

Grounded search with sources:

```bash
npm run gemini -- search "What is the current Finnish VAT rate for food?"
```
