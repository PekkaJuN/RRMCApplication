import { expect, it } from "vitest";
import { comparisonCsvUrl, comparisonPdfUrl, exportUrl, pdfLimits } from "./export";

const WEEKS = { unit: "week", from: "2026-W40", to: "2026-W41" } as const;
const OCTOBER = { unit: "month", from: "2026-10", to: "2026-10" } as const;

it("export AC13: the URLs of the three files of a week period", () => {
  expect(exportUrl("weeks", WEEKS)).toBe(
    "/api/export/totals?unit=week&from=2026-W40&to=2026-W41&by=week",
  );
  expect(exportUrl("months", WEEKS)).toBe(
    "/api/export/totals?unit=week&from=2026-W40&to=2026-W41&by=month",
  );
  expect(exportUrl("lines", WEEKS)).toBe("/api/export/lines?unit=week&from=2026-W40&to=2026-W41");
});

it("export AC13: the URLs of a month period", () => {
  expect(exportUrl("weeks", OCTOBER)).toBe(
    "/api/export/totals?unit=month&from=2026-10&to=2026-10&by=week",
  );
  expect(exportUrl("months", OCTOBER)).toBe(
    "/api/export/totals?unit=month&from=2026-10&to=2026-10&by=month",
  );
  expect(exportUrl("lines", OCTOBER)).toBe("/api/export/lines?unit=month&from=2026-10&to=2026-10");
});

it("date range AC20: the URLs of a date range", () => {
  const range = { unit: "range", from: "2026-10-15", to: "2026-11-14" } as const;

  expect(exportUrl("weeks", range)).toBe(
    "/api/export/totals?unit=range&from=2026-10-15&to=2026-11-14&by=week",
  );
  expect(exportUrl("months", range)).toBe(
    "/api/export/totals?unit=range&from=2026-10-15&to=2026-11-14&by=month",
  );
  expect(exportUrl("lines", range)).toBe(
    "/api/export/lines?unit=range&from=2026-10-15&to=2026-11-14",
  );
});

it("PDF export AC19: the URLs of the totals PDF files", () => {
  expect(exportUrl("weeksPdf", OCTOBER)).toBe(
    "/api/export/totals/pdf?unit=month&from=2026-10&to=2026-10&by=week",
  );
  expect(exportUrl("monthsPdf", OCTOBER)).toBe(
    "/api/export/totals/pdf?unit=month&from=2026-10&to=2026-10&by=month",
  );
});

it("PDF export AC21: the URL of the comparison PDF", () => {
  expect(comparisonPdfUrl({ month: "2026-10", kind: "mid" })).toBe(
    "/api/export/comparison/pdf?month=2026-10&period=mid",
  );
  expect(comparisonPdfUrl({ month: "2026-10", kind: "calendar" })).toBe(
    "/api/export/comparison/pdf?month=2026-10&period=calendar",
  );
});

it("PDF export AC20: a weekly PDF covers at most 31 days", () => {
  expect(pdfLimits("2026-10-01", "2026-10-31").weeks).toBe(true);
  expect(pdfLimits("2026-10-15", "2026-11-14").weeks).toBe(true);
  expect(pdfLimits("2026-10-01", "2026-11-01").weeks).toBe(false);
});

it("PDF export AC20: a monthly PDF covers at most 366 days", () => {
  expect(pdfLimits("2026-01-01", "2027-01-01").months).toBe(true);
  expect(pdfLimits("2026-01-01", "2027-01-02").months).toBe(false);
  expect(pdfLimits("2026-01-01", "2027-01-31").months).toBe(false);
});

it("PDF export AC20: a change to summer time does not move a day", () => {
  // Finland moves to summer time on 29 March 2026; the period is 31 days.
  expect(pdfLimits("2026-03-15", "2026-04-14").weeks).toBe(true);
  expect(pdfLimits("2026-03-15", "2026-04-15").weeks).toBe(false);
});

it("comparison CSV AC13, AC14: the URLs of the comparison CSV file", () => {
  expect(comparisonCsvUrl({ month: "2026-10", kind: "mid" }, false)).toBe(
    "/api/export/comparison?month=2026-10&period=mid",
  );
  expect(comparisonCsvUrl({ month: "2026-10", kind: "mid" }, true)).toBe(
    "/api/export/comparison?month=2026-10&period=mid&weeks=true",
  );
  expect(comparisonCsvUrl({ month: "2026-10", kind: "calendar" }, false)).toBe(
    "/api/export/comparison?month=2026-10&period=calendar",
  );
  expect(comparisonCsvUrl({ month: "2026-10", kind: "calendar" }, true)).toBe(
    "/api/export/comparison?month=2026-10&period=calendar&weeks=true",
  );
});
