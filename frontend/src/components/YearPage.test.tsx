import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it } from "vitest";
import { answerYearTotals, EMPTY_YEAR, YEAR_TOTALS } from "../test/year";
import { YearPage } from "./YearPage";

// Year with products spec PC4, PC6, PC7.

const table = () => screen.getByRole("table", { name: "Vuosi 2026" });
const row = (name: string) => within(table()).queryByText(name)?.closest("tr") ?? null;

it("year AC12: heading, note, CSV link and the year table, read-only", async () => {
  answerYearTotals();
  render(<YearPage />);

  await screen.findByRole("table", { name: "Vuosi 2026" });
  expect(screen.getByRole("heading", { name: "Vuosi tuotteineen 2026" })).toBeInTheDocument();
  expect(
    screen.getByText("Tarkistamattomia kuitteja: 2. Ne eivät ole mukana summissa."),
  ).toBeInTheDocument();
  const link = screen.getByRole("link", { name: "Vie CSV" });
  expect(link).toHaveAttribute("href", "/api/export/year");
  expect(link).toHaveAttribute("download");
  const headings = within(table())
    .getAllByRole("columnheader")
    .map((heading) => heading.textContent);
  expect(headings).toEqual([
    "Nimi",
    ...Array.from({ length: 12 }, (_, index) => `2026-${String(index + 1).padStart(2, "0")}`),
    "Vuosi",
  ]);
  const total = within(table()).getByRole("row", { name: /^Yhteensä/ });
  expect(within(total).getAllByRole("cell").at(-1)).toHaveTextContent("15,00 €");
  expect(screen.queryAllByRole("textbox")).toEqual([]);
  expect(screen.queryAllByRole("combobox")).toEqual([]);
  expect(screen.queryAllByRole("spinbutton")).toEqual([]);
  for (const button of screen.queryAllByRole("button")) {
    expect(button).toHaveAttribute("aria-expanded");
  }
});

it("year AC13: groups show their categories, categories hide their products", async () => {
  answerYearTotals();
  const user = userEvent.setup();
  render(<YearPage />);
  await screen.findByRole("table", { name: "Vuosi 2026" });

  expect(row("Juusto")).toBeInTheDocument();
  expect(row("Maito")).toBeInTheDocument();
  expect(row("Maito 1l")).not.toBeInTheDocument();

  const maito = screen.getByRole("button", { name: "Näytä tuotteet: Maito" });
  expect(maito).toHaveAttribute("aria-expanded", "false");
  await user.click(maito);
  const product = row("Maito 1l");
  expect(product).toBeInTheDocument();
  expect(within(product as HTMLElement).getAllByRole("cell")[0]).toHaveTextContent("5,00 €");
  expect(screen.getByRole("button", { name: "Piilota tuotteet: Maito" })).toHaveAttribute(
    "aria-expanded",
    "true",
  );

  await user.click(screen.getByRole("button", { name: "Piilota kategoriat: Maitotuotteet" }));
  expect(row("Juusto")).not.toBeInTheDocument();
  expect(row("Maito")).not.toBeInTheDocument();
  expect(row("Maito 1l")).not.toBeInTheDocument();
});

it("year AC14: an empty year says so, without a table or a CSV link", async () => {
  answerYearTotals(EMPTY_YEAR);
  render(<YearPage />);

  expect(
    await screen.findByText("Vuodelta 2026 ei ole vielä tarkistettuja kuitteja."),
  ).toBeInTheDocument();
  expect(
    screen.getByText("Tarkistamattomia kuitteja: 1. Ne eivät ole mukana summissa."),
  ).toBeInTheDocument();
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Vie CSV" })).not.toBeInTheDocument();
});

it("year AC15: no note without unreviewed receipts", async () => {
  answerYearTotals({ ...YEAR_TOTALS, unreviewed: 0 });
  render(<YearPage />);

  await screen.findByRole("table", { name: "Vuosi 2026" });
  expect(screen.queryByText(/Tarkistamattomia kuitteja/)).not.toBeInTheDocument();
});

it("year AC16: a failed request shows the backend's message as an alert", async () => {
  answerYearTotals(YEAR_TOTALS, {
    status: 500,
    body: { error: "internal_error", message: "Jokin meni pieleen." },
  });
  render(<YearPage />);

  expect(await screen.findByRole("alert")).toHaveTextContent("Jokin meni pieleen.");
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Vie CSV" })).not.toBeInTheDocument();
});

it("year AC17: the wide box, the sticky name column and wrapping names", async () => {
  answerYearTotals();
  render(<YearPage />);
  await screen.findByRole("table", { name: "Vuosi 2026" });

  expect(table().parentElement).toHaveClass("table-box", "table-box-wide");
  expect(table()).toHaveClass("archive-table");
});
