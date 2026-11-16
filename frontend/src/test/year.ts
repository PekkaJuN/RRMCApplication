import { http, HttpResponse } from "msw";
import type { ArchiveRow } from "../api/archive";
import type { YearTotals } from "../api/totals";
import { TOTALS } from "./archive";
import { server } from "./server";

/** Moves the archive fixture's rows to 2026: the same tree is the year spec's AC1. */
function rows(list: ArchiveRow[]): ArchiveRow[] {
  return list.map((row) => ({ ...row, children: rows(row.children) }));
}

/** The current year totals of the year with products spec's AC1 and AC2. */
export const YEAR_TOTALS: YearTotals = {
  ...TOTALS,
  year: 2026,
  months: Array.from({ length: 12 }, (_, index) => `2026-${String(index + 1).padStart(2, "0")}`),
  rows: rows(TOTALS.rows),
  unreviewed: 2,
};

/** The empty year of AC9. */
export const EMPTY_YEAR: YearTotals = {
  ...YEAR_TOTALS,
  rows: [],
  month_totals: Array.from({ length: 12 }, () => 0),
  total: 0,
  unreviewed: 1,
};

/** Answers GET /api/year/totals with `totals`, or with an error body and status. */
export function answerYearTotals(
  totals: YearTotals = YEAR_TOTALS,
  error?: { status: number; body: { error: string; message: string } },
): void {
  server.use(
    http.get("/api/year/totals", () =>
      error ? HttpResponse.json(error.body, { status: error.status }) : HttpResponse.json(totals),
    ),
  );
}
