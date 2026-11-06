/**
 * The period of the totals page (totals spec PC5, P5; date range spec PC1): whole months,
 * whole ISO weeks or a date range, in the API's format. The backend decides validity (week 53,
 * real days, order, length); this only reads the shape, so a bad address falls back to the
 * current month.
 */

import type { TotalsColumn } from "./api/totals";
import { formatDate, formatDayMonth } from "./format";
import { fi } from "./i18n/fi";

export type PeriodUnit = "month" | "week" | "range";

/** A table is always weeks or months, also for a date range. */
export type ColumnUnit = Exclude<PeriodUnit, "range">;

export interface Period {
  unit: PeriodUnit;
  from: string;
  to: string;
}

const MONTH = /^[0-9]{4}-(0[1-9]|1[0-2])$/;
const WEEK = /^[0-9]{4}-W(0[1-9]|[1-4][0-9]|5[0-3])$/;
const DAY = /^[0-9]{4}-[0-9]{2}-[0-9]{2}$/;
const SHAPES: Record<PeriodUnit, RegExp> = { month: MONTH, week: WEEK, range: DAY };

export function isUnitValue(unit: PeriodUnit, value: string): boolean {
  return SHAPES[unit].test(value);
}

/** The period in `?unit=...&from=...&to=...`, or null when it is incomplete or malformed. */
export function periodFromSearch(search: string): Period | null {
  const params = new URLSearchParams(search);
  const unit = params.get("unit");
  const from = params.get("from");
  const to = params.get("to");
  if ((unit !== "month" && unit !== "week" && unit !== "range") || from === null || to === null) {
    return null;
  }
  return isUnitValue(unit, from) && isUnitValue(unit, to) ? { unit, from, to } : null;
}

export function periodToSearch(period: Period): string {
  return `?unit=${period.unit}&from=${period.from}&to=${period.to}`;
}

function pad(value: number): string {
  return String(value).padStart(2, "0");
}

/** The calendar month of the local date `today`. */
export function currentMonth(today: Date): Period {
  const month = `${today.getFullYear()}-${pad(today.getMonth() + 1)}`;
  return { unit: "month", from: month, to: month };
}

/** The calendar month of the local date `today` as a date range. */
export function currentMonthRange(today: Date): Period {
  const month = currentMonth(today).from;
  const lastDay = new Date(today.getFullYear(), today.getMonth() + 1, 0).getDate();
  return { unit: "range", from: `${month}-01`, to: `${month}-${pad(lastDay)}` };
}

/** The ISO week of the local date `today`. */
export function currentWeek(today: Date): Period {
  // Work in UTC on the local calendar day, so daylight saving time cannot shift a day.
  const day = new Date(Date.UTC(today.getFullYear(), today.getMonth(), today.getDate()));
  const weekday = day.getUTCDay() || 7;
  // The Thursday of the same week decides the ISO year.
  day.setUTCDate(day.getUTCDate() + 4 - weekday);
  const year = day.getUTCFullYear();
  const dayOfYear = (day.getTime() - Date.UTC(year, 0, 1)) / 86_400_000;
  const week = `${year}-W${pad(Math.floor(dayOfYear / 7) + 1)}`;
  return { unit: "week", from: week, to: week };
}

/** `2026-W40` → `vk 40/2026`. */
export function weekLabel(key: string): string {
  const [year, week] = key.split("-W");
  return `vk ${Number(week)}/${year}`;
}

/** `2027-01` → `1/2027`. */
export function monthLabel(key: string): string {
  const [year, month] = key.split("-");
  return `${Number(month)}/${year}`;
}

/** A column heading; a partial column adds the mark and its days (totals PC4, budget PC10). */
export function columnHeading(column: TotalsColumn, unit: ColumnUnit): string {
  const name = unit === "week" ? weekLabel(column.key) : monthLabel(column.key);
  if (!column.partial) {
    return name;
  }
  // A partial column of a date range can cross a year, and then both days need theirs.
  const sameYear = column.start_date.slice(0, 4) === column.end_date.slice(0, 4);
  const first = (sameYear ? formatDayMonth : formatDate)(column.start_date);
  return `${name} ${fi.totals.partial} ${first}–${formatDate(column.end_date)}`;
}
