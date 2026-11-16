import { expect, it } from "vitest";
import { attention, finnishYear } from "./receiptsAttention";
import { ATTENTION_LIST, attentionReceipts, FUTURE_UNREVIEWED } from "./test/receipts";

// Note on old and undated unreviewed receipts (specs/features/unreviewed-receipts-note.md).

it("unreviewed-note AC1: counts undated and earlier unreviewed receipts", () => {
  expect(attention(ATTENTION_LIST, 2026)).toEqual({ undated: 1, earlier: 3, years: [2024, 2025] });
});

it("unreviewed-note AC2: undated receipts only", () => {
  expect(attention(attentionReceipts(1, 2, 3), 2026)).toEqual({
    undated: 1,
    earlier: 0,
    years: [],
  });
});

it("unreviewed-note AC3: earlier receipts only", () => {
  expect(attention(attentionReceipts(3, 4, 5, 6), 2026)).toEqual({
    undated: 0,
    earlier: 3,
    years: [2024, 2025],
  });
});

it("unreviewed-note AC4: reviewed, current and later receipts need no attention", () => {
  expect(attention([...attentionReceipts(2, 3, 7), FUTURE_UNREVIEWED], 2026)).toEqual({
    undated: 0,
    earlier: 0,
    years: [],
  });
});

it("unreviewed-note AC7: the year is Finnish", () => {
  expect(finnishYear(new Date("2025-12-31T22:30:00Z"))).toBe(2026);
  expect(finnishYear(new Date("2025-12-31T21:30:00Z"))).toBe(2025);
});
