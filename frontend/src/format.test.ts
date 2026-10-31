import { expect, it } from "vitest";
import { formatCents, formatCentsInput, formatDate, parseCents } from "./format";

it("AC30: amounts are euros with a decimal comma and no thousands separator", () => {
  expect([0, 5, 125, -40, -125, 123456].map(formatCents)).toEqual([
    "0,00 €",
    "0,05 €",
    "1,25 €",
    "-0,40 €",
    "-1,25 €",
    "1234,56 €",
  ]);
});

it("AC30: dates are day.month.year without leading zeros", () => {
  expect(formatDate("2026-10-05")).toBe("5.10.2026");
  expect(formatDate("2026-01-15")).toBe("15.1.2026");
});

// Line editing PC13.

it("line-editing AC27: amounts typed with a comma or a dot are read as cents", () => {
  const typed = ["1,25", "1.25", "-0,40", "3", "3,5", " 2,00 ", "0"];
  expect(typed.map(parseCents)).toEqual([125, 125, -40, 300, 350, 200, 0]);
});

it("line-editing AC27: -0 is read as 0", () => {
  expect(Object.is(parseCents("-0"), 0)).toBe(true);
});

it("line-editing AC27: other text is not an amount", () => {
  const typed = ["abc", "1,234", "1 234,00", ",5", "1,", "--1", ""];
  expect(typed.map(parseCents)).toEqual([null, null, null, null, null, null, null]);
});

it("line-editing AC27: an amount field shows a decimal comma and no euro sign", () => {
  expect([125, -40, 0, 5].map(formatCentsInput)).toEqual(["1,25", "-0,40", "0,00", "0,05"]);
});
