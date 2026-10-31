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

/** `2026-10-05` → `5.10.2026`. */
export function formatDate(isoDate: string): string {
  const [year, month, day] = isoDate.split("-");
  return `${Number(day)}.${Number(month)}.${year}`;
}
