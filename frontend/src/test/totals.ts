import { http, HttpResponse } from "msw";
import type { Totals, TotalsColumn } from "../api/totals";
import { server } from "./server";

function column(key: string, start: string, end: string, partial: boolean): TotalsColumn {
  return { key, start_date: start, end_date: end, partial };
}

/** The totals of October 2026 (totals spec, API shape): Ruoka with two categories, Juomat
 * without a group, and lines without a category. */
export const OCTOBER: Totals = {
  unit: "month",
  from: "2026-10",
  to: "2026-10",
  start_date: "2026-10-01",
  end_date: "2026-10-31",
  weeks: [
    column("2026-W40", "2026-10-01", "2026-10-04", true),
    column("2026-W41", "2026-10-05", "2026-10-11", false),
  ],
  months: [column("2026-10", "2026-10-01", "2026-10-31", false)],
  rows: [
    {
      kind: "group",
      id: 1,
      name: "Ruoka",
      weeks: [125, 300],
      months: [425],
      categories: [
        { kind: "category", id: 9, name: "Leivät", weeks: [0, 300], months: [300], categories: [] },
        {
          kind: "category",
          id: 2,
          name: "Maitotuotteet",
          weeks: [125, 0],
          months: [125],
          categories: [],
        },
      ],
    },
    {
      kind: "category",
      id: 20,
      name: "Juomat",
      weeks: [0, 123456],
      months: [123456],
      categories: [],
    },
    { kind: "none", id: null, name: null, weeks: [0, 199], months: [199], categories: [] },
  ],
  week_totals: [125, 123955],
  month_totals: [124080],
  unreviewed_receipts: 0,
  undated_receipts: 0,
  archived_years: [],
};

/** No lines in the period. */
export function emptyTotals(base: Totals = OCTOBER): Totals {
  return {
    ...base,
    rows: [],
    week_totals: base.weeks.map(() => 0),
    month_totals: base.months.map(() => 0),
  };
}

/**
 * Answer GET /api/totals with `answer(searchParams)` and record each request's query
 * (`unit=...&from=...&to=...`) in the returned list.
 */
export function answerTotals(
  answer: (params: URLSearchParams) => Response | Promise<Response> = () =>
    HttpResponse.json(OCTOBER),
): string[] {
  const queries: string[] = [];
  server.use(
    http.get("/api/totals", ({ request }) => {
      const params = new URL(request.url).searchParams;
      queries.push(params.toString());
      return answer(params);
    }),
  );
  return queries;
}
