import { expect, it } from "vitest";
import {
  currentMonth,
  currentWeek,
  monthLabel,
  periodFromSearch,
  periodToSearch,
  weekLabel,
} from "./period";

it("totals AC22: a month or week period is read from the address", () => {
  expect(periodFromSearch("?unit=month&from=2026-10&to=2026-12")).toEqual({
    unit: "month",
    from: "2026-10",
    to: "2026-12",
  });
  expect(periodFromSearch("?unit=week&from=2026-W40&to=2026-W41")).toEqual({
    unit: "week",
    from: "2026-W40",
    to: "2026-W41",
  });
});

it("totals AC22: an incomplete or malformed address gives no period", () => {
  const searches = [
    "",
    "?unit=week&from=bad",
    "?unit=week&from=2026-W40",
    "?unit=day&from=2026-10&to=2026-10",
    "?unit=month&from=2026-W40&to=2026-W40",
    "?unit=week&from=2026-10&to=2026-10",
    "?unit=month&from=2026-13&to=2026-13",
    "?unit=week&from=2026-W54&to=2026-W54",
  ];
  expect(searches.map(periodFromSearch)).toEqual(searches.map(() => null));
});

it("totals AC22: a period is written to the address", () => {
  expect(periodToSearch({ unit: "week", from: "2026-W40", to: "2026-W41" })).toBe(
    "?unit=week&from=2026-W40&to=2026-W41",
  );
});

it("totals AC14: the current month comes from the local date", () => {
  expect(currentMonth(new Date(2026, 10, 2))).toEqual({
    unit: "month",
    from: "2026-11",
    to: "2026-11",
  });
  expect(currentMonth(new Date(2027, 0, 1)).from).toBe("2027-01");
});

it("totals AC16: the current ISO week, also at the year boundaries", () => {
  expect(currentWeek(new Date(2026, 10, 2))).toEqual({
    unit: "week",
    from: "2026-W45",
    to: "2026-W45",
  });
  // Thu 1 Jan 2026 is in week 1 of 2026; Sun 3 Jan 2027 is in week 53 of 2026.
  expect(currentWeek(new Date(2026, 0, 1)).from).toBe("2026-W01");
  expect(currentWeek(new Date(2027, 0, 3)).from).toBe("2026-W53");
  // Mon 29 Dec 2025 is in week 1 of 2026.
  expect(currentWeek(new Date(2025, 11, 29)).from).toBe("2026-W01");
});

it("totals AC23: week and month labels without leading zeros", () => {
  expect(weekLabel("2026-W40")).toBe("vk 40/2026");
  expect(weekLabel("2027-W01")).toBe("vk 1/2027");
  expect(monthLabel("2026-12")).toBe("12/2026");
  expect(monthLabel("2027-01")).toBe("1/2027");
});
