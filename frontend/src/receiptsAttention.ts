import type { ReceiptSummary } from "./api/receipts";

// Note on old and undated unreviewed receipts (specs/features/unreviewed-receipts-note.md).

export interface Attention {
  /** Unreviewed receipts without a purchase date. */
  undated: number;
  /** Unreviewed receipts dated before the current year. */
  earlier: number;
  /** The years of the earlier receipts, each once, ascending. */
  years: number[];
}

const FINNISH_YEAR = new Intl.DateTimeFormat("fi-FI", {
  timeZone: "Europe/Helsinki",
  year: "numeric",
});

/** The year of `now` in Finland, as the backend counts the current year (PC1). */
export function finnishYear(now: Date): number {
  return Number(FINNISH_YEAR.format(now));
}

function dateYear(receipt: ReceiptSummary): number | null {
  return receipt.purchase_date === null ? null : Number(receipt.purchase_date.slice(0, 4));
}

/** Whether `receipt` is unreviewed and has no date or one before `year` (PC1). */
export function needsAttention(receipt: ReceiptSummary, year: number): boolean {
  if (receipt.reviewed) {
    return false;
  }
  const dated = dateYear(receipt);
  return dated === null || dated < year;
}

/** The counts of the note (PC2). */
export function attention(receipts: ReceiptSummary[], year: number): Attention {
  const needing = receipts.filter((receipt) => needsAttention(receipt, year));
  const years = needing.map(dateYear).filter((dated): dated is number => dated !== null);
  return {
    undated: needing.length - years.length,
    earlier: years.length,
    years: [...new Set(years)].sort((a, b) => a - b),
  };
}
