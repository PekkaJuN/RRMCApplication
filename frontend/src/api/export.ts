import type { Period } from "../period";

/** The export files of a period: the totals by week or by month, and the lines. */
export type ExportKind = "weeks" | "months" | "lines";

/** The download URL of an export file (export spec PC2–PC4). The browser fetches it
 * itself, so the file name comes from the backend's Content-Disposition. */
export function exportUrl(kind: ExportKind, period: Period): string {
  const query = new URLSearchParams({ unit: period.unit, from: period.from, to: period.to });
  if (kind === "lines") {
    return `/api/export/lines?${query.toString()}`;
  }
  query.set("by", kind === "weeks" ? "week" : "month");
  return `/api/export/totals?${query.toString()}`;
}
