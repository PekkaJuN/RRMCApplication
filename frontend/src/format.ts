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

/** `2026-10-05` → `5.10.2026`. */
export function formatDate(isoDate: string): string {
  const [year, month, day] = isoDate.split("-");
  return `${Number(day)}.${Number(month)}.${year}`;
}
