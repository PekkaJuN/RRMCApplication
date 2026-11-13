import type { ComparisonKind, ComparisonPeriod } from "../comparison";
import { apiGet, apiPut, type ApiResult } from "./client";
import type { TotalsColumn } from "./totals";

/** A group or a category without a group, with its monthly budget. */
export interface BudgetRow {
  kind: "group" | "category";
  id: number;
  name: string;
  amount_cents: number;
}

/** Mirrors the backend schema of GET /api/budget (budget spec, API shape). */
export interface Budget {
  rows: BudgetRow[];
  total_cents: number;
}

export interface WeekFigures {
  budget_cents: number;
  actual_cents: number;
}

/** A budget row, or the lines without a category (`kind` `none`, `name` null). */
export interface ComparisonRow {
  kind: "group" | "category" | "none";
  id: number | null;
  name: string | null;
  budget_cents: number;
  actual_cents: number;
  remaining_cents: number;
  /** In the order of `Comparison.weeks`. */
  weeks: WeekFigures[];
}

export type ComparisonTotal = Omit<ComparisonRow, "kind" | "id" | "name">;

/** Mirrors the backend schema of GET /api/budget/comparison (budget spec, API shape). */
export interface Comparison {
  month: string;
  period: ComparisonKind;
  start_date: string;
  end_date: string;
  weeks: TotalsColumn[];
  rows: ComparisonRow[];
  total: ComparisonTotal;
  unreviewed_receipts: number;
  undated_receipts: number;
  /** Archived years that overlap the period (archiving spec PC10). */
  archived_years: number[];
}

export function getBudget(): Promise<ApiResult<Budget>> {
  return apiGet<Budget>("/api/budget");
}

export function saveBudget(id: number, amountCents: number): Promise<ApiResult<Budget>> {
  return apiPut<Budget>(`/api/budget/${id}`, { amount_cents: amountCents });
}

export function getComparison(period: ComparisonPeriod): Promise<ApiResult<Comparison>> {
  const query = new URLSearchParams({ month: period.month });
  if (period.kind === "mid") {
    query.set("period", "mid");
  }
  return apiGet<Comparison>(`/api/budget/comparison?${query.toString()}`);
}
