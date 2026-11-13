import { http, HttpResponse } from "msw";
import type { ArchiveOverview, ArchiveResult, ArchiveTotals, ArchiveRow } from "../api/archive";
import { server } from "./server";

export const OVERVIEW: ArchiveOverview = {
  archived: [{ year: 2025, receipts: 12, lines: 140, images: 11 }],
  candidates: [
    { year: 2024, receipts: 3, lines: 20, images: 3, unreviewed: 1 },
    { year: 2023, receipts: 12, lines: 140, images: 11, unreviewed: 0 },
  ],
};

function months(values: Record<number, number>): number[] {
  return Array.from({ length: 12 }, (_, index) => values[index + 1] ?? 0);
}

function product(name: string, values: Record<number, number>): ArchiveRow {
  const sums = months(values);
  return {
    kind: "product",
    name,
    months: sums,
    total: sums.reduce((a, b) => a + b, 0),
    children: [],
  };
}

/** The year totals of the archiving spec's AC26. */
export const TOTALS: ArchiveTotals = {
  year: 2025,
  months: Array.from({ length: 12 }, (_, index) => `2025-${String(index + 1).padStart(2, "0")}`),
  rows: [
    {
      kind: "category",
      name: "Kahvi",
      months: months({ 3: 500 }),
      total: 500,
      children: [product("Kahvi 500g", { 3: 500 })],
    },
    {
      kind: "group",
      name: "Maitotuotteet",
      months: months({ 1: 900 }),
      total: 900,
      children: [
        {
          kind: "category",
          name: "Juusto",
          months: months({ 1: 400 }),
          total: 400,
          children: [product("Edam", { 1: 400 })],
        },
        {
          kind: "category",
          name: "Maito",
          months: months({ 1: 500 }),
          total: 500,
          children: [product("Maito 1l", { 1: 500 })],
        },
      ],
    },
    {
      kind: "none",
      name: null,
      months: months({ 3: 100 }),
      total: 100,
      children: [product("TUNTEMATON", { 3: 100 })],
    },
  ],
  month_totals: months({ 1: 900, 3: 600 }),
  total: 1500,
};

export interface ArchiveRequests {
  archived: number[];
  deleted: number[];
  /** How many times the overview was read. */
  overviews: number;
}

interface Answers {
  overview?: ArchiveOverview;
  /** The overview after a successful POST or DELETE, as the backend would answer then. */
  after?: ArchiveOverview;
  result?: ArchiveResult;
  /** An error body and status for POST, e.g. a 409 `unreviewed_receipts`. */
  archiveError?: { status: number; body: { error: string; message: string; count?: number } };
  /** Kept back until it resolves, to test a pending request. */
  hold?: Promise<void>;
}

/** Answers GET, POST and DELETE of /api/archive; returns the years as the requests arrive. */
export function answerArchive(answers: Answers = {}): ArchiveRequests {
  const requests: ArchiveRequests = { archived: [], deleted: [], overviews: 0 };
  let changed = false;
  server.use(
    http.get("/api/archive", () => {
      requests.overviews += 1;
      const overview = changed && answers.after ? answers.after : answers.overview;
      return HttpResponse.json(overview ?? OVERVIEW);
    }),
    http.post("/api/archive/:year", async ({ params }) => {
      const year = Number(params.year);
      requests.archived.push(year);
      await answers.hold;
      if (answers.archiveError) {
        return HttpResponse.json(answers.archiveError.body, {
          status: answers.archiveError.status,
        });
      }
      changed = true;
      return HttpResponse.json(
        answers.result ?? {
          year,
          receipts: 12,
          lines: 140,
          images_moved: 11,
          images_not_moved: [],
        },
      );
    }),
    http.delete("/api/archive/:year", async ({ params }) => {
      const year = Number(params.year);
      requests.deleted.push(year);
      await answers.hold;
      changed = true;
      return HttpResponse.json({ year, receipts: 12, lines: 140 });
    }),
  );
  return requests;
}

/** Answers GET /api/archive/:year/totals with `TOTALS` for 2025 and 404 for other years. */
export function answerArchiveTotals(): void {
  server.use(
    http.get("/api/archive/:year/totals", ({ params }) =>
      params.year === "2025"
        ? HttpResponse.json(TOTALS)
        : HttpResponse.json(
            { error: "not_found", message: "Pyydettyä kohdetta ei löydy." },
            { status: 404 },
          ),
    ),
  );
}
