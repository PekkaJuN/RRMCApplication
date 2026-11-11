import { act, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { answerComparison, OCTOBER_COMPARISON } from "../test/budget";
import { server } from "../test/server";
import { ComparisonPage } from "./ComparisonPage";

function setToday(today: Date) {
  // Only Date is faked, so fetch and MSW keep their real timers.
  vi.useFakeTimers({ toFake: ["Date"], now: today });
}

beforeEach(() => {
  setToday(new Date(2026, 10, 5, 12));
  window.history.replaceState(null, "", "/vertailu");
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

const monthInput = () => screen.getByLabelText("Kuukausi", { selector: "input" });

function changeMonth(month: string) {
  fireEvent.change(monthInput(), { target: { value: month } });
}

const showWeeks = () => screen.getByRole("button", { name: "Näytä viikot" });
const hideWeeks = () => screen.getByRole("button", { name: "Piilota viikot" });
const periodSelect = () => screen.getByRole("combobox", { name: "Jakso" });

it("budget AC19: opens on the current month with the month table only", async () => {
  const queries = answerComparison();
  render(<ComparisonPage />);

  expect(screen.getByRole("heading", { name: "Vertailu" })).toBeInTheDocument();
  expect(await screen.findByRole("table", { name: "Kuukausi" })).toBeInTheDocument();
  expect(screen.queryByRole("table", { name: "Viikot" })).not.toBeInTheDocument();
  expect(periodSelect()).toHaveValue("calendar");
  expect(monthInput()).toHaveValue("2026-11");
  expect(window.location.search).toBe("?month=2026-11");
  expect(queries).toEqual(["month=2026-11"]);
});

it("budget AC19: a chosen month stays in the address and a reload keeps it", async () => {
  const queries = answerComparison();
  const { unmount } = render(<ComparisonPage />);
  await screen.findByRole("table", { name: "Kuukausi" });

  changeMonth("2026-10");

  expect(window.location.search).toBe("?month=2026-10");
  await vi.waitFor(() => expect(queries).toEqual(["month=2026-11", "month=2026-10"]));
  unmount();
  render(<ComparisonPage />);
  expect(monthInput()).toHaveValue("2026-10");
  await screen.findByRole("table", { name: "Kuukausi" });
});

it("budget AC19: a bad address opens the current month", async () => {
  window.history.replaceState(null, "", "/vertailu?month=bad");
  const queries = answerComparison();
  render(<ComparisonPage />);

  await screen.findByRole("table", { name: "Kuukausi" });
  expect(window.location.search).toBe("?month=2026-11");
  expect(queries).toEqual(["month=2026-11"]);
});

it("budget AC19: an emptied month input sends no request", async () => {
  const queries = answerComparison();
  render(<ComparisonPage />);
  await screen.findByRole("table", { name: "Kuukausi" });

  changeMonth("");

  expect(monthInput()).toHaveValue("");
  expect(window.location.search).toBe("?month=2026-11");
  // A later choice settles the requests, so a stray one for the empty value would show here.
  changeMonth("2026-10");
  await vi.waitFor(() => expect(queries).toHaveLength(2));
  expect(queries).toEqual(["month=2026-11", "month=2026-10"]);
});

it("budget AC19: the back button shows the earlier month", async () => {
  const queries = answerComparison();
  render(<ComparisonPage />);
  await screen.findByRole("table", { name: "Kuukausi" });

  popTo("/vertailu?month=2026-08");

  await vi.waitFor(() => expect(queries).toEqual(["month=2026-11", "month=2026-08"]));
  expect(monthInput()).toHaveValue("2026-08");
});

it("budget AC25: the button shows and hides the weeks without a request", async () => {
  const queries = answerComparison();
  const user = userEvent.setup();
  render(<ComparisonPage />);
  await screen.findByRole("table", { name: "Kuukausi" });
  expect(showWeeks()).toHaveAttribute("aria-expanded", "false");

  await user.click(showWeeks());

  expect(screen.getByRole("table", { name: "Viikot" })).toBeInTheDocument();
  expect(hideWeeks()).toHaveAttribute("aria-expanded", "true");
  expect(queries).toHaveLength(1);

  await user.click(hideWeeks());

  expect(screen.queryByRole("table", { name: "Viikot" })).not.toBeInTheDocument();
  expect(showWeeks()).toHaveAttribute("aria-expanded", "false");
});

it("budget AC25: changing the month keeps the weeks open or hidden", async () => {
  const queries = answerComparison();
  const user = userEvent.setup();
  render(<ComparisonPage />);
  await screen.findByRole("table", { name: "Kuukausi" });

  changeMonth("2026-10");
  await vi.waitFor(() => expect(queries).toHaveLength(2));
  expect(screen.queryByRole("table", { name: "Viikot" })).not.toBeInTheDocument();

  await user.click(showWeeks());
  changeMonth("2026-09");

  await vi.waitFor(() => expect(queries).toHaveLength(3));
  expect(await screen.findByRole("table", { name: "Viikot" })).toBeInTheDocument();
});

it("budget AC25: after a reload the weeks are hidden", async () => {
  answerComparison();
  const user = userEvent.setup();
  const { unmount } = render(<ComparisonPage />);
  await screen.findByRole("table", { name: "Kuukausi" });
  await user.click(showWeeks());

  unmount();
  render(<ComparisonPage />);

  await screen.findByRole("table", { name: "Kuukausi" });
  expect(screen.queryByRole("table", { name: "Viikot" })).not.toBeInTheDocument();
});

it("budget AC20: shows the counts", async () => {
  answerComparison({ ...OCTOBER_COMPARISON, unreviewed_receipts: 2, undated_receipts: 1 });
  render(<ComparisonPage />);

  expect(await screen.findByText("Tarkistamattomia kuitteja, ei mukana: 2")).toHaveAttribute(
    "role",
    "status",
  );
  expect(screen.getByText("Kuitteja ilman päivää (ei mukana): 1")).toHaveAttribute(
    "role",
    "status",
  );
});

it("budget AC20: hides the counts at 0", async () => {
  answerComparison();
  render(<ComparisonPage />);

  await screen.findByRole("table", { name: "Kuukausi" });
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
});

it("budget PC5: a failed request shows the message", async () => {
  server.use(
    http.get("/api/budget/comparison", () =>
      HttpResponse.json(
        { error: "invalid_period", message: "Jakso on virheellinen." },
        { status: 422 },
      ),
    ),
  );
  render(<ComparisonPage />);

  expect(await screen.findByRole("alert")).toHaveTextContent("Jakso on virheellinen.");
});

it.each([
  [new Date(2026, 10, 6, 12), "2026-10", "15.10.2026–14.11.2026"],
  [new Date(2026, 10, 20, 12), "2026-11", "15.11.2026–14.12.2026"],
  [new Date(2027, 0, 10, 12), "2026-12", "15.12.2026–14.1.2027"],
])("budget AC31: choosing 15.–14. on %s selects the period", async (today, month, dates) => {
  setToday(today);
  const queries = answerComparison();
  const user = userEvent.setup();
  render(<ComparisonPage />);
  await screen.findByRole("table", { name: "Kuukausi" });

  await user.selectOptions(periodSelect(), "15.–14.");

  expect(window.location.search).toBe(`?month=${month}&period=mid`);
  expect(await screen.findByText(`Jakso: ${dates}`)).toBeInTheDocument();
  expect(queries.at(-1)).toBe(`month=${month}&period=mid`);
  expect(monthInput()).toHaveValue(month);
});

it("budget AC31: choosing a kind fills an emptied month input", async () => {
  setToday(new Date(2026, 10, 6, 12));
  const queries = answerComparison();
  const user = userEvent.setup();
  render(<ComparisonPage />);
  await screen.findByRole("table", { name: "Kuukausi" });
  changeMonth("");

  await user.selectOptions(periodSelect(), "15.–14.");

  expect(monthInput()).toHaveValue("2026-10");
  await vi.waitFor(() => expect(queries.at(-1)).toBe("month=2026-10&period=mid"));
});

it("budget AC31: changing the month keeps 15.–14. and a reload keeps both", async () => {
  setToday(new Date(2026, 10, 6, 12));
  const queries = answerComparison();
  const user = userEvent.setup();
  const { unmount } = render(<ComparisonPage />);
  await screen.findByRole("table", { name: "Kuukausi" });
  await user.selectOptions(periodSelect(), "15.–14.");

  changeMonth("2026-08");

  expect(window.location.search).toBe("?month=2026-08&period=mid");
  await vi.waitFor(() => expect(queries.at(-1)).toBe("month=2026-08&period=mid"));
  unmount();
  render(<ComparisonPage />);
  expect(periodSelect()).toHaveValue("mid");
  expect(monthInput()).toHaveValue("2026-08");
  await screen.findByRole("table", { name: "Kuukausi" });
});

it("budget AC31: Kalenterikuukausi returns to the current month", async () => {
  setToday(new Date(2026, 10, 6, 12));
  window.history.replaceState(null, "", "/vertailu?month=2026-10&period=mid");
  answerComparison();
  const user = userEvent.setup();
  render(<ComparisonPage />);
  await screen.findByRole("table", { name: "Kuukausi" });

  await user.selectOptions(periodSelect(), "Kalenterikuukausi");

  expect(window.location.search).toBe("?month=2026-11");
});

it("budget AC33: a month the backend refuses shows the error and the controls work", async () => {
  setToday(new Date(2026, 10, 6, 12));
  window.history.replaceState(null, "", "/vertailu?month=9999-01&period=mid");
  server.use(
    http.get("/api/budget/comparison", () =>
      HttpResponse.json(
        { error: "invalid_period", message: "Jakso on virheellinen." },
        { status: 422 },
      ),
    ),
  );
  const user = userEvent.setup();
  render(<ComparisonPage />);

  expect(await screen.findByRole("alert")).toHaveTextContent("Jakso on virheellinen.");
  expect(window.location.search).toBe("?month=9999-01&period=mid");
  expect(screen.queryByRole("table", { name: "Kuukausi" })).not.toBeInTheDocument();

  answerComparison();
  await user.selectOptions(periodSelect(), "Kalenterikuukausi");

  expect(await screen.findByRole("table", { name: "Kuukausi" })).toBeInTheDocument();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  expect(window.location.search).toBe("?month=2026-11");
});

it("budget AC31: changing the kind keeps the weeks open", async () => {
  setToday(new Date(2026, 10, 6, 12));
  answerComparison();
  const user = userEvent.setup();
  render(<ComparisonPage />);
  await screen.findByRole("table", { name: "Kuukausi" });
  await user.click(showWeeks());

  await user.selectOptions(periodSelect(), "15.–14.");

  expect(await screen.findByRole("table", { name: "Viikot" })).toBeInTheDocument();
});

it("budget AC31: changing the kind keeps the weeks hidden", async () => {
  setToday(new Date(2026, 10, 6, 12));
  answerComparison();
  const user = userEvent.setup();
  render(<ComparisonPage />);
  await screen.findByRole("table", { name: "Kuukausi" });

  await user.selectOptions(periodSelect(), "15.–14.");

  expect(await screen.findByText("Jakso: 15.10.2026–14.11.2026")).toBeInTheDocument();
  expect(screen.queryByRole("table", { name: "Viikot" })).not.toBeInTheDocument();
  expect(showWeeks()).toHaveAttribute("aria-expanded", "false");
});

it.each([
  ["/vertailu?month=bad&period=mid", "?month=2026-10&period=mid"],
  ["/vertailu?month=2026-10&period=bad", "?month=2026-11"],
])("budget AC31: the address %s", async (path, search) => {
  setToday(new Date(2026, 10, 6, 12));
  window.history.replaceState(null, "", path);
  answerComparison();
  render(<ComparisonPage />);

  await screen.findByRole("table", { name: "Kuukausi" });
  expect(window.location.search).toBe(search);
});

// PDF export (PDF export spec PC10).

const pdfLink = () => screen.queryByRole("link", { name: "Vie vertailu (PDF)" });

it("PDF export AC21: the link downloads the PDF of the shown period", async () => {
  window.history.replaceState(null, "", "/vertailu?month=2026-10&period=mid");
  answerComparison();
  render(<ComparisonPage />);

  await screen.findByRole("table", { name: "Kuukausi" });
  const link = pdfLink();
  expect(link).toHaveAttribute("href", "/api/export/comparison/pdf?month=2026-10&period=mid");
  expect(link).toHaveAttribute("download", "");
});

it("PDF export AC21: the link follows a new month", async () => {
  answerComparison();
  render(<ComparisonPage />);
  await screen.findByRole("table", { name: "Kuukausi" });
  expect(pdfLink()).toHaveAttribute(
    "href",
    "/api/export/comparison/pdf?month=2026-11&period=calendar",
  );

  changeMonth("2026-09");

  await vi.waitFor(() =>
    expect(pdfLink()).toHaveAttribute(
      "href",
      "/api/export/comparison/pdf?month=2026-09&period=calendar",
    ),
  );
});

it("PDF export AC21: no link while the comparison answer is an error", async () => {
  server.use(
    http.get("/api/budget/comparison", () =>
      HttpResponse.json(
        { error: "invalid_period", message: "Jakso on virheellinen." },
        { status: 422 },
      ),
    ),
  );
  render(<ComparisonPage />);

  await screen.findByRole("alert");
  expect(pdfLink()).not.toBeInTheDocument();
});

it("PDF export AC21: opening the week table does not change the link", async () => {
  answerComparison();
  const user = userEvent.setup();
  render(<ComparisonPage />);
  await screen.findByRole("table", { name: "Kuukausi" });
  const before = pdfLink()?.getAttribute("href");

  await user.click(showWeeks());

  expect(pdfLink()?.getAttribute("href")).toBe(before);
});

// Comparison CSV export (comparison CSV export spec PC9).

const csvLink = () => screen.queryByRole("link", { name: "Vie vertailu (CSV)" });
const weeksBox = () => screen.getByRole("checkbox", { name: "Viikot mukaan" });

it("comparison CSV AC13: the link and the unchecked box of the shown period", async () => {
  window.history.replaceState(null, "", "/vertailu?month=2026-10&period=mid");
  answerComparison();
  render(<ComparisonPage />);

  await screen.findByRole("table", { name: "Kuukausi" });
  const link = csvLink();
  expect(link).toHaveAttribute("href", "/api/export/comparison?month=2026-10&period=mid");
  expect(link).toHaveAttribute("download", "");
  expect(weeksBox()).not.toBeChecked();
  expect(pdfLink()).toHaveAttribute("href", "/api/export/comparison/pdf?month=2026-10&period=mid");
});

it("comparison CSV AC14: the box adds and removes the weeks", async () => {
  window.history.replaceState(null, "", "/vertailu?month=2026-10&period=mid");
  answerComparison();
  const user = userEvent.setup();
  render(<ComparisonPage />);
  await screen.findByRole("table", { name: "Kuukausi" });

  await user.click(weeksBox());

  expect(weeksBox()).toBeChecked();
  expect(csvLink()).toHaveAttribute(
    "href",
    "/api/export/comparison?month=2026-10&period=mid&weeks=true",
  );

  await user.click(weeksBox());

  expect(csvLink()).toHaveAttribute("href", "/api/export/comparison?month=2026-10&period=mid");
});

it("comparison CSV AC15: the link keeps the shown period until the new answer", async () => {
  window.history.replaceState(null, "", "/vertailu?month=2026-10");
  answerComparison();
  render(<ComparisonPage />);
  await screen.findByRole("table", { name: "Kuukausi" });
  let release = () => {};
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  server.use(
    http.get("/api/budget/comparison", async () => {
      await gate;
      return HttpResponse.json({ ...OCTOBER_COMPARISON, month: "2026-11" });
    }),
  );

  changeMonth("2026-11");

  expect(csvLink()).toHaveAttribute("href", "/api/export/comparison?month=2026-10&period=calendar");
  release();
  await vi.waitFor(() =>
    expect(csvLink()).toHaveAttribute(
      "href",
      "/api/export/comparison?month=2026-11&period=calendar",
    ),
  );
});
