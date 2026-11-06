/**
 * The period of the Vertailu page (budget spec PC6, P8): a calendar month, or the period from
 * the 15th to the 14th named after its starting month. The backend computes the dates; this
 * only reads the address and finds the period that holds today.
 */

import { isUnitValue } from "./period";

export type ComparisonKind = "calendar" | "mid";

export interface ComparisonPeriod {
  month: string;
  kind: ComparisonKind;
}

const MID_PERIOD_START_DAY = 15;

function monthKey(year: number, monthIndex: number): string {
  return `${year}-${String(monthIndex + 1).padStart(2, "0")}`;
}

/** The period of `kind` that holds the local date `today`. */
export function currentComparison(today: Date, kind: ComparisonKind): ComparisonPeriod {
  const beforeStart = kind === "mid" && today.getDate() < MID_PERIOD_START_DAY;
  // Day 1 of the month, so stepping back a month cannot overflow; month -1 is last December.
  const first = new Date(today.getFullYear(), today.getMonth() - (beforeStart ? 1 : 0), 1);
  return { month: monthKey(first.getFullYear(), first.getMonth()), kind };
}

/** The period in the address. An unknown kind opens the current calendar month, and a bad
 * month the current period of its kind. */
export function comparisonFromSearch(search: string, today: Date): ComparisonPeriod {
  const params = new URLSearchParams(search);
  const kind = params.get("period") ?? "calendar";
  if (kind !== "calendar" && kind !== "mid") {
    return currentComparison(today, "calendar");
  }
  const month = params.get("month");
  return month !== null && isUnitValue("month", month)
    ? { month, kind }
    : currentComparison(today, kind);
}

export function comparisonToSearch(period: ComparisonPeriod): string {
  const kind = period.kind === "mid" ? "&period=mid" : "";
  return `?month=${period.month}${kind}`;
}
