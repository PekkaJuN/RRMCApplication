import { expect, it } from "vitest";
import { answerYearTotals, YEAR_TOTALS } from "../test/year";
import { getYearTotals, yearCsvUrl } from "./totals";

// Year with products spec T8: the client of GET /api/year/totals and the CSV link.

it("year AC12: reads the current year totals", async () => {
  answerYearTotals();

  expect(await getYearTotals()).toEqual({ ok: true, data: YEAR_TOTALS });
});

it("year AC16: an error keeps the backend's code and message", async () => {
  answerYearTotals(YEAR_TOTALS, {
    status: 500,
    body: { error: "internal_error", message: "Jokin meni pieleen." },
  });

  expect(await getYearTotals()).toEqual({
    ok: false,
    error: { code: "internal_error", message: "Jokin meni pieleen." },
  });
});

it("year AC12: the CSV file comes from /api/export/year", () => {
  expect(yearCsvUrl()).toBe("/api/export/year");
});
