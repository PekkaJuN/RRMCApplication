# 0005. PDF export with reportlab, read back in tests with pdfminer.six

- Status: accepted
- Date: 2026-11-09

## Context

The PDF export ([spec](../../specs/features/pdf-export.md), PRD FR-48) makes three files:
weekly totals (A4 landscape), monthly totals and the budget comparison (A4 portrait). They
must be easy to read: text at least 9 pt, tables that continue on the next page with their
headings repeated, and month blocks that are never split over two pages unless one is
taller than a page. The text holds `ä`, `ö` and `€`. The files are made on this machine
only (NFR-1), through the exporter interface (FR-27), and the tests must check their
content.

The options were:

1. **reportlab** (BSD): page layout with tables, repeated heading rows and blocks kept
   together. Standard fonts with WinAnsi encoding.
2. **fpdf2** (LGPL): a smaller API with tables and unbreakable sections. Its standard fonts
   cover Latin-1 only, which has no `€`, so a TrueType font file would be shipped.
3. **WeasyPrint** (BSD): HTML and CSS to PDF. Needs Pango and other system libraries in the
   backend image.
4. **The browser's print dialog** with a print style sheet: no dependency, but the result
   depends on the browser and its settings, the file does not go through the exporter
   interface, and tests cannot check it.

## Decision

- Use **reportlab** for the PDF files. Use its `platypus` layout: `Table` with
  `repeatRows`, `KeepTogether` for month blocks, `Paragraph` cells so long names wrap, and
  a canvas that writes `Sivu n/total` after all pages are known. Use the standard fonts
  `Helvetica` and `Helvetica-Bold`; no font file is shipped.
- Use **pdfminer.six** (MIT) as a development dependency to read the files in tests: page
  size, text per page, character sizes and positions, and metadata.
- A spike on 2026-11-09 (reportlab 5.1.0, pdfminer.six 20260107, `python:3.12-slim-bookworm`)
  confirmed every point above.

## Consequences

- One runtime dependency, pure Python, on top of Pillow, which the backend already has. No
  system packages; the backend image changes only by its lock file.
- Licences (checked 2026-11-09 from the package metadata): reportlab BSD, its dependency
  charset-normalizer MIT; pdfminer.six MIT, its dependency cryptography Apache-2.0 or
  BSD-3-Clause (development only). All permissive, no copyleft. The open-source reportlab
  toolkit is enough; the commercial ReportLab PLUS is not needed.
- The standard fonts cover Finnish, Swedish and `€`. A character outside WinAnsi in a
  category name would not show correctly. If that becomes a need, a TrueType font is
  registered instead (a new ADR).
- Tests check the real file content, not the code that builds it.
- `pip-audit` covers both new packages.
