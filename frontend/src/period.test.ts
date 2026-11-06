import { expect, it } from "vitest";
import {
  columnHeading,
  currentMonth,
  currentMonthRange,
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

// Date range spec.

it("date range AC16: a range is read from the address and written back", () => {
  const search = "?unit=range&from=2026-10-15&to=2026-11-14";
  const period = periodFromSearch(search);

  expect(period).toEqual({ unit: "range", from: "2026-10-15", to: "2026-11-14" });
  expect(period && periodToSearch(period)).toBe(search);
});

it("date range AC18: a range of another shape gives no period", () => {
  const addresses = [
    "?unit=range&from=2026-10&to=2026-11-14",
    "?unit=range&from=2026-10-15",
    "?unit=range&from=2026-W40&to=2026-11-14",
    "?unit=range&from=15.10.2026&to=2026-11-14",
  ];

  expect(addresses.map(periodFromSearch)).toEqual(addresses.map(() => null));
});

it("date range AC19: a day that is not real is left for the backend", () => {
  expect(periodFromSearch("?unit=range&from=2026-02-30&to=2026-03-01")).toEqual({
    unit: "range",
    from: "2026-02-30",
    to: "2026-03-01",
  });
});

it("date range AC13: the current month as days, by the local date", () => {
  expect(currentMonthRange(new Date(2026, 10, 6))).toEqual({
    unit: "range",
    from: "2026-11-01",
    to: "2026-11-30",
  });
  expect(currentMonthRange(new Date(2028, 1, 10)).to).toBe("2028-02-29");
  expect(currentMonthRange(new Date(2026, 11, 31)).to).toBe("2026-12-31");
});

it("date range AC21: a partial column's heading across a month and a year", () => {
  const column = (key: string, start_date: string, end_date: string) => ({
    key,
    start_date,
    end_date,
    partial: true,
  });

  expect(columnHeading(column("2026-W44", "2026-10-28", "2026-11-01"), "week")).toBe(
    "vk 44/2026 (osittainen) 28.10.–1.11.2026",
  );
  expect(columnHeading(column("2026-W53", "2026-12-30", "2027-01-02"), "week")).toBe(
    "vk 53/2026 (osittainen) 30.12.2026–2.1.2027",
  );
});
