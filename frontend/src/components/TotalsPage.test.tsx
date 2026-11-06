import { act, fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { server } from "../test/server";
import { answerTotals, emptyTotals, OCTOBER } from "../test/totals";
import { TotalsPage } from "./TotalsPage";

beforeEach(() => {
  // Only Date is faked, so fetch and MSW keep their real timers.
  vi.useFakeTimers({ toFake: ["Date"], now: new Date(2026, 10, 2, 12) });
  window.history.replaceState(null, "", "/yhteenveto");
});

afterEach(() => {
  vi.useRealTimers();
});

function popTo(path: string) {
  act(() => {
    window.history.replaceState(null, "", path);
    window.dispatchEvent(new PopStateEvent("popstate"));
  });
}

it("totals AC14: opens on the current month and shows both tables", async () => {
  const queries = answerTotals();
  render(<TotalsPage />);

  expect(screen.getByRole("heading", { name: "Yhteenveto" })).toBeInTheDocument();
  expect(screen.getByRole("combobox", { name: "Jakso" })).toHaveValue("month");
  expect(screen.getByLabelText("Alkaen")).toHaveValue("2026-11");
  expect(screen.getByLabelText("Päättyen")).toHaveValue("2026-11");
  const weeks = await screen.findByRole("table", { name: "Viikot" });
  expect(within(weeks).getByRole("rowheader", { name: /Juomat/ })).toBeInTheDocument();
  const months = screen.getByRole("table", { name: "Kuukaudet" });
  expect(within(months).getByText("1240,80 €")).toBeInTheDocument();
  expect(queries).toEqual(["unit=month&from=2026-11&to=2026-11"]);
  expect(window.location.search).toBe("?unit=month&from=2026-11&to=2026-11");
});

it("totals AC15: expanding a group shows its categories in both tables", async () => {
  answerTotals();
  const user = userEvent.setup();
  render(<TotalsPage />);
  const weeks = await screen.findByRole("table", { name: "Viikot" });
  const months = screen.getByRole("table", { name: "Kuukaudet" });

  await user.click(within(weeks).getByRole("button", { name: "Näytä kategoriat: Ruoka" }));

  expect(within(weeks).getByRole("rowheader", { name: "Leivät" })).toBeInTheDocument();
  expect(within(months).getByRole("rowheader", { name: "Leivät" })).toBeInTheDocument();
  expect(within(months).getByRole("button", { name: "Piilota kategoriat: Ruoka" })).toHaveAttribute(
    "aria-expanded",
    "true",
  );
});

it("totals AC18: a period without lines shows the empty text and no tables", async () => {
  answerTotals(() => HttpResponse.json(emptyTotals()));
  render(<TotalsPage />);

  expect(await screen.findByText("Ei ostoksia valitulla jaksolla.")).toBeInTheDocument();
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
});

it("totals AC18: a refused period shows the backend's message", async () => {
  answerTotals(() =>
    HttpResponse.json(
      { error: "invalid_period", message: "Jakso on virheellinen." },
      { status: 422 },
    ),
  );
  render(<TotalsPage />);

  expect(await screen.findByRole("alert")).toHaveTextContent("Jakso on virheellinen.");
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
});

it("totals AC18: an unreachable backend shows the network message", async () => {
  server.use(http.get("/api/totals", () => HttpResponse.error()));
  render(<TotalsPage />);

  expect(await screen.findByRole("alert")).toHaveTextContent("Taustapalveluun ei saada yhteyttä.");
});

it("totals AC20, AC21: the counts are shown when they are not 0", async () => {
  answerTotals(() =>
    HttpResponse.json({ ...OCTOBER, unreviewed_receipts: 2, undated_receipts: 1 }),
  );
  render(<TotalsPage />);

  expect(await screen.findByText("Tarkistamattomia kuitteja jaksolla: 2")).toHaveAttribute(
    "role",
    "status",
  );
  expect(screen.getByText("Kuitteja ilman päivää (ei mukana): 1")).toHaveAttribute(
    "role",
    "status",
  );
});

it("totals AC20, AC21: counts of 0 are not shown", async () => {
  answerTotals();
  render(<TotalsPage />);

  await screen.findByRole("table", { name: "Viikot" });
  expect(screen.queryByText(/Tarkistamattomia/)).not.toBeInTheDocument();
  expect(screen.queryByText(/ilman päivää/)).not.toBeInTheDocument();
});

it("totals AC16: choosing weeks requests them and keeps them in the address", async () => {
  const queries = answerTotals();
  const user = userEvent.setup();
  render(<TotalsPage />);
  await screen.findByRole("table", { name: "Viikot" });

  await user.selectOptions(screen.getByRole("combobox", { name: "Jakso" }), "week");

  expect(screen.getByLabelText("Alkaen")).toHaveValue("2026-W45");
  expect(screen.getByLabelText("Päättyen")).toHaveValue("2026-W45");
  fireEvent.change(screen.getByLabelText("Alkaen"), { target: { value: "2026-W40" } });
  fireEvent.change(screen.getByLabelText("Päättyen"), { target: { value: "2026-W41" } });

  // The two requests run at the same time, so they may arrive in either order.
  await vi.waitFor(() => expect(queries).toHaveLength(4));
  expect([...queries].sort()).toEqual([
    "unit=month&from=2026-11&to=2026-11",
    "unit=week&from=2026-W40&to=2026-W41",
    "unit=week&from=2026-W40&to=2026-W45",
    "unit=week&from=2026-W45&to=2026-W45",
  ]);
  expect(window.location.search).toBe("?unit=week&from=2026-W40&to=2026-W41");
});

it("totals AC22: the period comes from the address and back restores the previous one", async () => {
  window.history.replaceState(null, "", "/yhteenveto?unit=week&from=2026-W40&to=2026-W41");
  const queries = answerTotals();
  render(<TotalsPage />);

  expect(screen.getByRole("combobox", { name: "Jakso" })).toHaveValue("week");
  expect(screen.getByLabelText("Alkaen")).toHaveValue("2026-W40");
  await screen.findByRole("table", { name: "Viikot" });

  popTo("/yhteenveto?unit=month&from=2026-09&to=2026-10");

  expect(screen.getByLabelText("Alkaen")).toHaveValue("2026-09");
  expect(screen.getByLabelText("Päättyen")).toHaveValue("2026-10");
  await vi.waitFor(() => expect(queries).toHaveLength(2));
  expect(queries).toEqual([
    "unit=week&from=2026-W40&to=2026-W41",
    "unit=month&from=2026-09&to=2026-10",
  ]);
});

it("totals AC22: a change adds a history entry", async () => {
  const queries = answerTotals();
  render(<TotalsPage />);
  await screen.findByRole("table", { name: "Viikot" });
  const before = window.history.length;

  fireEvent.change(screen.getByLabelText("Alkaen"), { target: { value: "2026-10" } });

  expect(window.history.length).toBe(before + 1);
  expect(window.location.search).toBe("?unit=month&from=2026-10&to=2026-11");
  // Wait for the request, so it cannot reach the next test's handler.
  await vi.waitFor(() => expect(queries).toHaveLength(2));
});

it("totals AC22: a bad address opens the current month", async () => {
  window.history.replaceState(null, "", "/yhteenveto?unit=week&from=bad");
  const queries = answerTotals();
  render(<TotalsPage />);

  await screen.findByRole("table", { name: "Viikot" });
  expect(queries).toEqual(["unit=month&from=2026-11&to=2026-11"]);
  expect(window.location.search).toBe("?unit=month&from=2026-11&to=2026-11");
});

it("totals P6: an emptied input sends no request", async () => {
  const queries = answerTotals();
  render(<TotalsPage />);
  await screen.findByRole("table", { name: "Viikot" });

  fireEvent.change(screen.getByLabelText("Alkaen"), { target: { value: "" } });

  expect(screen.getByLabelText("Alkaen")).toHaveValue("");
  expect(queries).toHaveLength(1);
  expect(window.location.search).toBe("?unit=month&from=2026-11&to=2026-11");
});

it("totals P6: an older answer arriving last is not shown", async () => {
  let releaseFirst: () => void = () => undefined;
  const firstHeld = new Promise<void>((resolve) => {
    releaseFirst = resolve;
  });
  answerTotals(async (params) => {
    if (params.get("from") === "2026-11") {
      await firstHeld;
      return HttpResponse.json({ ...OCTOBER, unreviewed_receipts: 7 });
    }
    return HttpResponse.json({ ...OCTOBER, unreviewed_receipts: 3 });
  });
  render(<TotalsPage />);

  fireEvent.change(screen.getByLabelText("Alkaen"), { target: { value: "2026-10" } });
  expect(await screen.findByText("Tarkistamattomia kuitteja jaksolla: 3")).toBeInTheDocument();
  releaseFirst();

  await new Promise((resolve) => setTimeout(resolve, 50));
  expect(screen.queryByText("Tarkistamattomia kuitteja jaksolla: 7")).not.toBeInTheDocument();
  expect(screen.getByText("Tarkistamattomia kuitteja jaksolla: 3")).toBeInTheDocument();
});

function exportLinks(): [string, string | null, string | null][] {
  return screen
    .getAllByRole("link")
    .map((link) => [
      link.textContent ?? "",
      link.getAttribute("href"),
      link.getAttribute("download"),
    ]);
}

it("export AC13: three export links of the shown period follow a new period", async () => {
  answerTotals();
  window.history.replaceState(null, "", "/yhteenveto?unit=week&from=2026-W40&to=2026-W41");
  render(<TotalsPage />);
  await screen.findByRole("table", { name: "Viikot" });

  expect(exportLinks()).toEqual([
    [
      "Vie viikkosummat (CSV)",
      "/api/export/totals?unit=week&from=2026-W40&to=2026-W41&by=week",
      "",
    ],
    [
      "Vie kuukausisummat (CSV)",
      "/api/export/totals?unit=week&from=2026-W40&to=2026-W41&by=month",
      "",
    ],
    ["Vie rivit (CSV)", "/api/export/lines?unit=week&from=2026-W40&to=2026-W41", ""],
  ]);

  fireEvent.change(screen.getByLabelText("Päättyen"), { target: { value: "2026-W42" } });

  await vi.waitFor(() =>
    expect(screen.getByRole("link", { name: "Vie rivit (CSV)" })).toHaveAttribute(
      "href",
      "/api/export/lines?unit=week&from=2026-W40&to=2026-W42",
    ),
  );
  expect(screen.getByRole("link", { name: "Vie viikkosummat (CSV)" })).toHaveAttribute(
    "href",
    "/api/export/totals?unit=week&from=2026-W40&to=2026-W42&by=week",
  );
});

it("export AC14: the links are shown for a period without lines", async () => {
  answerTotals(() => HttpResponse.json(emptyTotals()));
  render(<TotalsPage />);

  await screen.findByText("Ei ostoksia valitulla jaksolla.");
  expect(screen.getAllByRole("link")).toHaveLength(3);
});

it("export AC14: no link while the period is refused", async () => {
  answerTotals(() =>
    HttpResponse.json(
      { error: "invalid_period", message: "Jakso on virheellinen." },
      { status: 422 },
    ),
  );
  render(<TotalsPage />);

  await screen.findByRole("alert");
  expect(screen.queryByRole("link")).not.toBeInTheDocument();
});

it("export AC14: no link when the totals cannot be loaded", async () => {
  server.use(http.get("/api/totals", () => HttpResponse.error()));
  render(<TotalsPage />);

  await screen.findByRole("alert");
  expect(screen.queryByRole("link")).not.toBeInTheDocument();
});

it("export AC13: while a new period loads, the links keep the period of the shown totals", async () => {
  let release: () => void = () => undefined;
  const waiting = new Promise<void>((resolve) => {
    release = resolve;
  });
  answerTotals(async (params) => {
    if (params.get("to") === "2026-W42") {
      await waiting;
    }
    return HttpResponse.json(OCTOBER);
  });
  window.history.replaceState(null, "", "/yhteenveto?unit=week&from=2026-W40&to=2026-W41");
  render(<TotalsPage />);
  await screen.findByRole("table", { name: "Viikot" });

  fireEvent.change(screen.getByLabelText("Päättyen"), { target: { value: "2026-W42" } });

  expect(screen.getByRole("link", { name: "Vie rivit (CSV)" })).toHaveAttribute(
    "href",
    "/api/export/lines?unit=week&from=2026-W40&to=2026-W41",
  );
  release();
  await vi.waitFor(() =>
    expect(screen.getByRole("link", { name: "Vie rivit (CSV)" })).toHaveAttribute(
      "href",
      "/api/export/lines?unit=week&from=2026-W40&to=2026-W42",
    ),
  );
});

it("styling AC1: the Yhteenveto page has no inline style", async () => {
  answerTotals();
  const { container } = render(<TotalsPage />);

  await screen.findByRole("table", { name: "Viikot" });
  expect(screen.getAllByRole("link")).toHaveLength(3);
  expect(container.querySelectorAll("[style]")).toHaveLength(0);
});

// Date range spec.

const RANGE_PATH = "/yhteenveto?unit=range&from=2026-10-15&to=2026-11-14";
const RANGE_SEARCH = "?unit=range&from=2026-10-15&to=2026-11-14";

it("date range AC13: choosing Aikaväli selects the current month as days", async () => {
  const queries = answerTotals();
  const user = userEvent.setup();
  render(<TotalsPage />);
  await screen.findByRole("table", { name: "Viikot" });

  await user.selectOptions(screen.getByRole("combobox", { name: "Jakso" }), "Aikaväli");

  expect(screen.getByLabelText("Alkaen")).toHaveValue("01.11.2026");
  expect(screen.getByLabelText("Päättyen")).toHaveValue("30.11.2026");
  expect(window.location.search).toBe("?unit=range&from=2026-11-01&to=2026-11-30");
  await vi.waitFor(() => expect(queries).toContain("unit=range&from=2026-11-01&to=2026-11-30"));
});

it("date range AC16: an address opens the range", async () => {
  window.history.replaceState(null, "", RANGE_PATH);
  const queries = answerTotals();
  render(<TotalsPage />);

  expect(screen.getByRole("combobox", { name: "Jakso" })).toHaveValue("range");
  expect(screen.getByLabelText("Alkaen")).toHaveValue("15.10.2026");
  expect(screen.getByLabelText("Päättyen")).toHaveValue("14.11.2026");
  await screen.findByRole("table", { name: "Viikot" });
  expect(queries).toEqual(["unit=range&from=2026-10-15&to=2026-11-14"]);
});

it("date range AC17: the back button shows the earlier range", async () => {
  window.history.replaceState(null, "", RANGE_PATH);
  answerTotals();
  render(<TotalsPage />);
  await screen.findByRole("table", { name: "Viikot" });

  popTo("/yhteenveto?unit=range&from=2026-09-01&to=2026-09-30");

  expect(screen.getByLabelText("Alkaen")).toHaveValue("01.09.2026");
  expect(screen.getByLabelText("Päättyen")).toHaveValue("30.09.2026");
});

it.each([
  "/yhteenveto?unit=range&from=2026-10&to=2026-11-14",
  "/yhteenveto?unit=range&from=2026-10-15",
])("date range AC18: a malformed address %s opens the current month", async (path) => {
  window.history.replaceState(null, "", path);
  answerTotals();
  render(<TotalsPage />);

  expect(await screen.findByRole("table", { name: "Viikot" })).toBeInTheDocument();
  expect(window.location.search).toBe("?unit=month&from=2026-11&to=2026-11");
});

it("date range AC19: a refused range shows the error, no tables and no links", async () => {
  window.history.replaceState(null, "", "/yhteenveto?unit=range&from=2026-02-30&to=2026-03-01");
  server.use(
    http.get("/api/totals", () =>
      HttpResponse.json(
        { error: "invalid_period", message: "Jakso on virheellinen." },
        { status: 422 },
      ),
    ),
  );
  render(<TotalsPage />);

  expect(await screen.findByRole("alert")).toHaveTextContent("Jakso on virheellinen.");
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
  expect(screen.queryByRole("link")).not.toBeInTheDocument();
  expect(screen.getByLabelText("Alkaen")).toHaveValue("30.02.2026");
});

it("date range AC20: the export links follow the shown range", async () => {
  window.history.replaceState(null, "", RANGE_PATH);
  answerTotals();
  render(<TotalsPage />);

  const lines = await screen.findByRole("link", { name: "Vie rivit (CSV)" });

  expect(lines).toHaveAttribute(
    "href",
    "/api/export/lines?unit=range&from=2026-10-15&to=2026-11-14",
  );
  expect(screen.getByRole("link", { name: "Vie viikkosummat (CSV)" })).toHaveAttribute(
    "href",
    "/api/export/totals?unit=range&from=2026-10-15&to=2026-11-14&by=week",
  );
  expect(screen.getByRole("link", { name: "Vie kuukausisummat (CSV)" })).toHaveAttribute(
    "href",
    "/api/export/totals?unit=range&from=2026-10-15&to=2026-11-14&by=month",
  );
});

/** Pick a day from the calendar of the field `index`: 0 Alkaen, 1 Päättyen. */
function pick(index: number, day: string) {
  const picker = document.querySelectorAll<HTMLInputElement>('input[type="date"]')[index];
  if (picker === undefined) {
    throw new Error("no picker");
  }
  fireEvent.change(picker, { target: { value: day } });
}

it("date range AC14: each picked day loads the range", async () => {
  window.history.replaceState(null, "", "/yhteenveto?unit=range&from=2026-11-01&to=2026-11-30");
  const queries = answerTotals();
  render(<TotalsPage />);
  await screen.findByRole("table", { name: "Viikot" });

  pick(0, "2026-10-15");
  await vi.waitFor(() => expect(window.location.search).toContain("from=2026-10-15"));
  pick(1, "2026-11-14");

  await vi.waitFor(() =>
    expect(queries).toEqual([
      "unit=range&from=2026-11-01&to=2026-11-30",
      "unit=range&from=2026-10-15&to=2026-11-30",
      "unit=range&from=2026-10-15&to=2026-11-14",
    ]),
  );
  expect(window.location.search).toBe(RANGE_SEARCH);
  expect(screen.getByLabelText("Alkaen")).toHaveValue("15.10.2026");
});

it("date range AC15: the text cannot be edited", async () => {
  window.history.replaceState(null, "", RANGE_PATH);
  const queries = answerTotals();
  const user = userEvent.setup();
  HTMLInputElement.prototype.showPicker = vi.fn();
  render(<TotalsPage />);
  await screen.findByRole("table", { name: "Viikot" });
  const from = screen.getByLabelText("Alkaen");

  await user.type(from, "1");
  pick(0, "");

  expect(from).toHaveValue("15.10.2026");
  expect(queries).toEqual(["unit=range&from=2026-10-15&to=2026-11-14"]);
  expect(window.location.search).toBe(RANGE_SEARCH);
  expect(screen.getByRole("table", { name: "Viikot" })).toBeInTheDocument();
});

it("date range AC17: a changed range goes back with its fields and tables", async () => {
  window.history.replaceState(null, "", RANGE_PATH);
  const queries = answerTotals();
  render(<TotalsPage />);
  await screen.findByRole("table", { name: "Viikot" });

  pick(0, "2026-10-20");
  await vi.waitFor(() => expect(window.location.search).toContain("from=2026-10-20"));
  popTo(RANGE_PATH);

  expect(screen.getByLabelText("Alkaen")).toHaveValue("15.10.2026");
  expect(await screen.findByRole("table", { name: "Viikot" })).toBeInTheDocument();
  await vi.waitFor(() => expect(queries.at(-1)).toBe("unit=range&from=2026-10-15&to=2026-11-14"));
});

it("date range AC19: Alkaen after Päättyen shows the error, no tables and no links", async () => {
  window.history.replaceState(null, "", RANGE_PATH);
  answerTotals((params) =>
    params.get("from") === "2026-12-01"
      ? HttpResponse.json(
          { error: "invalid_period", message: "Jakso on virheellinen." },
          { status: 422 },
        )
      : HttpResponse.json(OCTOBER),
  );
  render(<TotalsPage />);
  await screen.findByRole("table", { name: "Viikot" });

  pick(0, "2026-12-01");

  expect(await screen.findByRole("alert")).toHaveTextContent("Jakso on virheellinen.");
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
  expect(screen.queryByRole("link")).not.toBeInTheDocument();
});
