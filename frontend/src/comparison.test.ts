import { expect, it } from "vitest";
import { comparisonFromSearch, comparisonToSearch, currentComparison } from "./comparison";

const TODAY = new Date(2026, 10, 6, 12);

it("budget AC19: the current calendar month", () => {
  expect(currentComparison(TODAY, "calendar")).toEqual({ month: "2026-11", kind: "calendar" });
});

it.each([
  [new Date(2026, 10, 6, 12), "2026-10"],
  [new Date(2026, 10, 14, 23), "2026-10"],
  [new Date(2026, 10, 15, 0), "2026-11"],
  [new Date(2026, 10, 20, 12), "2026-11"],
  [new Date(2027, 0, 10, 12), "2026-12"],
])("budget AC31: the 15–14 period that holds %s", (today, month) => {
  expect(currentComparison(today, "mid")).toEqual({ month, kind: "mid" });
});

it("budget AC19: a calendar period has only the month in the address", () => {
  expect(comparisonToSearch({ month: "2026-10", kind: "calendar" })).toBe("?month=2026-10");
});

it("budget AC31: a 15–14 period has the kind in the address", () => {
  expect(comparisonToSearch({ month: "2026-10", kind: "mid" })).toBe("?month=2026-10&period=mid");
});

it.each([
  ["?month=2026-10", { month: "2026-10", kind: "calendar" }],
  ["?month=2026-10&period=mid", { month: "2026-10", kind: "mid" }],
  ["", { month: "2026-11", kind: "calendar" }],
  ["?month=bad", { month: "2026-11", kind: "calendar" }],
  ["?month=2026-13", { month: "2026-11", kind: "calendar" }],
  ["?month=bad&period=mid", { month: "2026-10", kind: "mid" }],
  ["?period=mid", { month: "2026-10", kind: "mid" }],
  ["?month=2026-10&period=bad", { month: "2026-11", kind: "calendar" }],
])("budget AC19, AC31: the address %s", (search, expected) => {
  expect(comparisonFromSearch(search, TODAY)).toEqual(expected);
});
