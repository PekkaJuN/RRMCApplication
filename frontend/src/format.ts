/**
 * Money and dates as the receipt pages show them (receipt-review PC10). Integer arithmetic
 * and string splitting only: `Intl` uses another minus sign and spaces, and `Date` could move
 * a date by the time zone.
 */

/** `-40` → `-0,40 €`; no thousands separator. */
export function formatCents(cents: number): string {
  const sign = cents < 0 ? "-" : "";
  const absolute = Math.abs(cents);
  const euros = Math.trunc(absolute / 100);
  const rest = String(absolute % 100).padStart(2, "0");
  return `${sign}${euros},${rest} €`;
}

/** `-40` → `-0,40`: an amount field's value (line-editing PC13). */
export function formatCentsInput(cents: number): string {
  return formatCents(cents).slice(0, -" €".length);
}

// Optional minus, euros, and optionally a comma or dot with one or two cent digits.
const AMOUNT = /^\s*(-?)([0-9]+)(?:[.,]([0-9]{1,2}))?\s*$/;

/** `1,25` or `1.25` → `125`; null for anything else (line-editing PC13). No `parseFloat`. */
export function parseCents(text: string): number | null {
  const match = AMOUNT.exec(text);
  if (!match) {
    return null;
  }
  const [, sign, euros, fraction = ""] = match;
  const cents = Number(euros) * 100 + Number(fraction.padEnd(2, "0"));
  // `-0` is 0, so the request body never holds a negative zero.
  return sign && cents !== 0 ? -cents : cents;
}

/** `2026-10-01` → `1.10.`: the first day of a partial column (totals spec PC4). */
export function formatDayMonth(isoDate: string): string {
  const [, month, day] = isoDate.split("-");
  return `${Number(day)}.${Number(month)}.`;
}

/** `2026-10-05` → `5.10.2026`. */
export function formatDate(isoDate: string): string {
  const [year, month, day] = isoDate.split("-");
  return `${Number(day)}.${Number(month)}.${year}`;
}

/** `2026-10-05` → `05.10.2026`: the text of a date field (date field PC1). */
export function dateToText(date: string): string {
  return date.split("-").reverse().join(".");
}

const DATE_TEXT = /^([0-9]{1,2})\.([0-9]{1,2})\.([0-9]{4})$/;

/** `5.10.2026` → `2026-10-05`, or null when the text is not a real day (date field PC2). */
export function parseDateText(text: string): string | null {
  const match = DATE_TEXT.exec(text.trim());
  if (match === null) {
    return null;
  }
  const [, dayText = "", monthText = "", yearText = ""] = match;
  const [day, month, year] = [Number(dayText), Number(monthText), Number(yearText)];
  // Not `Date.UTC`: it maps the years 0–99 to the 1900s.
  const date = new Date(0);
  date.setUTCFullYear(year, month - 1, day);
  if (year === 0 || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) {
    return null;
  }
  return `${yearText}-${monthText.padStart(2, "0")}-${dayText.padStart(2, "0")}`;
}
