import { http, HttpResponse } from "msw";
import type { Budget, Comparison, ComparisonRow } from "../api/budget";
import { server } from "./server";

export const BUDGET: Budget = {
  rows: [
    { kind: "group", id: 1, name: "Ruoka", amount_cents: 40000 },
    { kind: "group", id: 7, name: "Auto", amount_cents: 0 },
    { kind: "category", id: 30, name: "Juomat", amount_cents: 5000 },
  ],
  total_cents: 45000,
};

/** Answers the budget endpoints; returns the saved `[id, cents]` pairs as the requests
 * arrive. A save updates the rows and the total, as the backend does. `holdFirstSave` keeps
 * the first answer back until it resolves. */
export function answerBudget(holdFirstSave?: Promise<void>): [number, number][] {
  const saves: [number, number][] = [];
  let budget = BUDGET;
  server.use(
    http.get("/api/budget", () => HttpResponse.json(budget)),
    http.put("/api/budget/:id", async ({ params, request }) => {
      const id = Number(params.id);
      const { amount_cents: cents } = (await request.json()) as { amount_cents: number };
      saves.push([id, cents]);
      if (saves.length === 1) {
        await holdFirstSave;
      }
      if (cents < 0) {
        return HttpResponse.json(
          { error: "invalid_amount", message: "Summa ei kelpaa." },
          { status: 422 },
        );
      }
      const rows = budget.rows.map((row) =>
        row.id === id ? { ...row, amount_cents: cents } : row,
      );
      budget = { rows, total_cents: rows.reduce((sum, row) => sum + row.amount_cents, 0) };
      return HttpResponse.json(budget);
    }),
  );
  return saves;
}

const JUOMAT: ComparisonRow = {
  kind: "category",
  id: 30,
  name: "Juomat",
  budget_cents: 5000,
  actual_cents: 5100,
  remaining_cents: -100,
  weeks: [
    { budget_cents: 645, actual_cents: 5100 },
    { budget_cents: 1129, actual_cents: 1129 },
  ],
};

const RUOKA: ComparisonRow = {
  kind: "group",
  id: 1,
  name: "Ruoka",
  budget_cents: 40000,
  actual_cents: 12500,
  remaining_cents: 27500,
  weeks: [
    { budget_cents: 5161, actual_cents: 12500 },
    { budget_cents: 9032, actual_cents: 0 },
  ],
};

/** October 2026, cut to two weeks: Ruoka within its budget and Juomat over it. */
export const OCTOBER_COMPARISON: Comparison = {
  month: "2026-10",
  period: "calendar",
  start_date: "2026-10-01",
  end_date: "2026-10-31",
  weeks: [
    { key: "2026-W40", start_date: "2026-10-01", end_date: "2026-10-04", partial: true },
    { key: "2026-W41", start_date: "2026-10-05", end_date: "2026-10-11", partial: false },
  ],
  rows: [RUOKA, JUOMAT],
  total: {
    budget_cents: 45000,
    actual_cents: 17600,
    remaining_cents: 27400,
    weeks: [
      { budget_cents: 5806, actual_cents: 17600 },
      { budget_cents: 10161, actual_cents: 1129 },
    ],
  },
  unreviewed_receipts: 0,
  undated_receipts: 0,
};

/** Answers the comparison from its query, as the backend does for the dates; returns the
 * query strings in order. */
export function answerComparison(answer: Comparison = OCTOBER_COMPARISON): string[] {
  const queries: string[] = [];
  server.use(
    http.get("/api/budget/comparison", ({ request }) => {
      const url = new URL(request.url);
      queries.push(url.search.slice(1));
      const month = url.searchParams.get("month") ?? "";
      const mid = url.searchParams.get("period") === "mid";
      const [year, monthNumber] = month.split("-").map(Number) as [number, number];
      const next =
        monthNumber === 12
          ? `${year + 1}-01`
          : `${year}-${String(monthNumber + 1).padStart(2, "0")}`;
      return HttpResponse.json({
        ...answer,
        month,
        period: mid ? "mid" : "calendar",
        start_date: mid ? `${month}-15` : `${month}-01`,
        end_date: mid ? `${next}-14` : answer.end_date,
      });
    }),
  );
  return queries;
}
