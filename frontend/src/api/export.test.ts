import { expect, it } from "vitest";
import { exportUrl } from "./export";

const WEEKS = { unit: "week", from: "2026-W40", to: "2026-W41" } as const;
const OCTOBER = { unit: "month", from: "2026-10", to: "2026-10" } as const;

it("export AC13: the URLs of the three files of a week period", () => {
  expect(exportUrl("weeks", WEEKS)).toBe(
    "/api/export/totals?unit=week&from=2026-W40&to=2026-W41&by=week",
  );
  expect(exportUrl("months", WEEKS)).toBe(
    "/api/export/totals?unit=week&from=2026-W40&to=2026-W41&by=month",
  );
  expect(exportUrl("lines", WEEKS)).toBe("/api/export/lines?unit=week&from=2026-W40&to=2026-W41");
});

it("export AC13: the URLs of a month period", () => {
  expect(exportUrl("weeks", OCTOBER)).toBe(
    "/api/export/totals?unit=month&from=2026-10&to=2026-10&by=week",
  );
  expect(exportUrl("months", OCTOBER)).toBe(
    "/api/export/totals?unit=month&from=2026-10&to=2026-10&by=month",
  );
  expect(exportUrl("lines", OCTOBER)).toBe("/api/export/lines?unit=month&from=2026-10&to=2026-10");
});
