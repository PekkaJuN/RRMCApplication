import { expect, it } from "vitest";
import {
  dateToText,
  formatCents,
  formatCentsInput,
  formatDate,
  formatDayMonth,
  parseCents,
  parseDateText,
} from "./format";

it("totals AC17: a day without its year", () => {
  expect(["2026-10-01", "2026-12-28"].map(formatDayMonth)).toEqual(["1.10.", "28.12."]);
});

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

// Date field PC1, PC2.

it("date-field AC1: a date shows as dd.mm.yyyy with leading zeros", () => {
  expect(dateToText("2026-10-05")).toBe("05.10.2026");
  expect(dateToText("")).toBe("");
});

it("date-field AC2: a typed date is read with or without leading zeros", () => {
  const typed = ["05.10.2026", " 5.10.2026 ", "5.1.2026"];
  expect(typed.map(parseDateText)).toEqual(["2026-10-05", "2026-10-05", "2026-01-05"]);
});

it("date-field AC3: a leap day exists only in a leap year", () => {
  const typed = ["29.02.2028", "29.02.2027", "29.02.2000", "29.02.1900"];
  expect(typed.map(parseDateText)).toEqual(["2028-02-29", null, "2000-02-29", null]);
});

it("date-field AC4: other text is not a date", () => {
  const typed = [
    "",
    "30.02.2026",
    "32.01.2026",
    "01.13.2026",
    "00.01.2026",
    "01.00.2026",
    "01.01.0000",
    "1.1.26",
    "2026-10-05",
    "05/10/2026",
    "abc",
    "٠٥.١٠.٢٠٢٦",
  ];
  expect(typed.map(parseDateText)).toEqual(typed.map(() => null));
});

it("date-field AC4: a year below 100 is not moved to the 1900s", () => {
  expect(parseDateText("05.10.0099")).toBe("0099-10-05");
});
