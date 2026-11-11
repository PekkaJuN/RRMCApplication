import type { ComparisonPeriod } from "../comparison";
import type { Period } from "../period";

/** The export files of a period: the totals by week or by month as CSV or PDF, and the
 * lines. */
export type ExportKind = "weeks" | "months" | "lines" | "weeksPdf" | "monthsPdf";

const TOTALS_FILES: Record<Exclude<ExportKind, "lines">, { path: string; by: string }> = {
  weeks: { path: "/api/export/totals", by: "week" },
  months: { path: "/api/export/totals", by: "month" },
  weeksPdf: { path: "/api/export/totals/pdf", by: "week" },
  monthsPdf: { path: "/api/export/totals/pdf", by: "month" },
};

/** The download URL of an export file (export spec PC2–PC4, PDF export spec PC2). The
 * browser fetches it itself, so the file name comes from the backend's
 * Content-Disposition. */
export function exportUrl(kind: ExportKind, period: Period): string {
  const query = new URLSearchParams({ unit: period.unit, from: period.from, to: period.to });
  if (kind === "lines") {
    return `/api/export/lines?${query.toString()}`;
  }
  const file = TOTALS_FILES[kind];
  query.set("by", file.by);
  return `${file.path}?${query.toString()}`;
}

/** The download URL of the comparison PDF (PDF export spec PC3, PC10). */
export function comparisonPdfUrl(period: ComparisonPeriod): string {
  const query = new URLSearchParams({ month: period.month, period: period.kind });
  return `/api/export/comparison/pdf?${query.toString()}`;
}

/** The download URL of the comparison CSV file, with the weeks when `weeks` (comparison CSV
 * export spec PC9). */
export function comparisonCsvUrl(period: ComparisonPeriod, weeks: boolean): string {
  const query = new URLSearchParams({ month: period.month, period: period.kind });
  if (weeks) {
    query.set("weeks", "true");
  }
  return `/api/export/comparison?${query.toString()}`;
}

// The backend's limits (PDF export spec PC8); the page only decides what to show.
const WEEKLY_PDF_DAYS = 31;
const MONTHLY_PDF_DAYS = 366;
const DAY_MS = 24 * 60 * 60 * 1000;

/** Whether each totals PDF of the period from `startDate` to `endDate` (`YYYY-MM-DD`, both
 * included) is within its limit (PDF export spec PC9). */
export function pdfLimits(startDate: string, endDate: string): { weeks: boolean; months: boolean } {
  const days = (dayNumber(endDate) - dayNumber(startDate)) / DAY_MS + 1;
  return { weeks: days <= WEEKLY_PDF_DAYS, months: days <= MONTHLY_PDF_DAYS };
}

/** UTC midnight of the day: a date-only ISO string is always read as UTC, so a change to
 * summer time cannot move it. */
function dayNumber(isoDate: string): number {
  return Date.parse(isoDate);
}
