import { expect, it } from "vitest";
import { formatCents, formatDate } from "./format";

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
