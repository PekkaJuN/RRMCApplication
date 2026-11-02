import type { Period } from "../period";
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
}

export function getTotals(period: Period): Promise<ApiResult<Totals>> {
  const query = new URLSearchParams({ unit: period.unit, from: period.from, to: period.to });
  return apiGet<Totals>(`/api/totals?${query.toString()}`);
}
