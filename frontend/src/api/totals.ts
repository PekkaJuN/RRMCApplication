import type { Period } from "../period";
import type { ArchiveTotals } from "./archive";
import { apiGet, type ApiResult } from "./client";

/** A week or month column, clipped to the period; `partial` when it was clipped. */
export interface TotalsColumn {
  key: string;
  start_date: string;
  end_date: string;
  partial: boolean;
}

/** A group, a category, or the lines without a category (`kind` `none`, `name` null). */
export interface TotalsRow {
  kind: "group" | "category" | "none";
  id: number | null;
  name: string | null;
  /** Cents per column, in the order of `Totals.weeks` and `Totals.months`. */
  weeks: number[];
  months: number[];
  categories: TotalsRow[];
}

/** Mirrors the backend schema of GET /api/totals (totals spec, API shape). */
export interface Totals {
  unit: Period["unit"];
  from: string;
  to: string;
  start_date: string;
  end_date: string;
  weeks: TotalsColumn[];
  months: TotalsColumn[];
  rows: TotalsRow[];
  week_totals: number[];
  month_totals: number[];
  unreviewed_receipts: number;
  undated_receipts: number;
  /** Archived years that overlap the period; their receipts are left out (archiving PC10). */
  archived_years: number[];
}

export function getTotals(period: Period): Promise<ApiResult<Totals>> {
  const query = new URLSearchParams({ unit: period.unit, from: period.from, to: period.to });
  return apiGet<Totals>(`/api/totals?${query.toString()}`);
}

/** The current year's totals per group, category and product, in the archived year's shape,
 * with the unreviewed receipts of the year that are not in them (year with products spec). */
export interface YearTotals extends ArchiveTotals {
  unreviewed: number;
}

export function getYearTotals(): Promise<ApiResult<YearTotals>> {
  return apiGet<YearTotals>("/api/year/totals");
}

/** The download URL of the current year's CSV file (year with products spec PC5). */
export function yearCsvUrl(): string {
  return "/api/export/year";
}
