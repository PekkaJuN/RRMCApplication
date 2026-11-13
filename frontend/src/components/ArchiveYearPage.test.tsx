import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it } from "vitest";
import { answerArchiveTotals } from "../test/archive";
import { ArchiveYearPage } from "./ArchiveYearPage";

// Archiving spec PC15.

const table = () => screen.getByRole("table", { name: "Vuosi 2025" });
/** The row whose name is `name`; a row's accessible name starts with its toggle's label. */
const row = (name: string) => within(table()).queryByText(name)?.closest("tr") ?? null;

it("archiving AC39: the year's totals with 12 months, Vuosi and a CSV link, read-only", async () => {
  answerArchiveTotals();
  render(<ArchiveYearPage year={2025} />);

  await screen.findByRole("table", { name: "Vuosi 2025" });
  const headings = within(table())
    .getAllByRole("columnheader")
    .map((heading) => heading.textContent);
  expect(headings).toEqual([
    "Nimi",
    ...Array.from({ length: 12 }, (_, index) => `2025-${String(index + 1).padStart(2, "0")}`),
    "Vuosi",
  ]);
  const link = screen.getByRole("link", { name: "Vie CSV" });
  expect(link).toHaveAttribute("href", "/api/export/archive/2025");
  expect(link).toHaveAttribute("download");
  expect(screen.queryAllByRole("textbox")).toEqual([]);
  expect(screen.queryAllByRole("combobox")).toEqual([]);
  expect(screen.queryAllByRole("spinbutton")).toEqual([]);
  for (const button of screen.queryAllByRole("button")) {
    expect(button).toHaveAttribute("aria-expanded");
  }
  const total = within(table()).getByRole("row", { name: /^Yhteensä/ });
  expect(within(total).getAllByRole("cell").at(-1)).toHaveTextContent("15,00 €");
});

it("archiving AC40: groups show their categories, categories hide their products", async () => {
  answerArchiveTotals();
  const user = userEvent.setup();
  render(<ArchiveYearPage year={2025} />);
  await screen.findByRole("table", { name: "Vuosi 2025" });

  expect(row("Juusto")).toBeInTheDocument();
  expect(row("Maito")).toBeInTheDocument();
  expect(row("Maito 1l")).not.toBeInTheDocument();

  const maito = screen.getByRole("button", { name: "Näytä tuotteet: Maito" });
  expect(maito).toHaveAttribute("aria-expanded", "false");
  await user.click(maito);
  const product = row("Maito 1l");
  expect(product).toBeInTheDocument();
  expect(within(product as HTMLElement).getAllByRole("cell")[0]).toHaveTextContent("5,00 €");
  expect(
    within(product as HTMLElement)
      .getAllByRole("cell")
      .at(-1),
  ).toHaveTextContent("5,00 €");
  expect(screen.getByRole("button", { name: "Piilota tuotteet: Maito" })).toHaveAttribute(
    "aria-expanded",
    "true",
  );

  await user.click(screen.getByRole("button", { name: "Piilota kategoriat: Maitotuotteet" }));
  expect(row("Juusto")).not.toBeInTheDocument();
  expect(row("Maito")).not.toBeInTheDocument();
  expect(row("Maito 1l")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Näytä kategoriat: Maitotuotteet" })).toHaveAttribute(
    "aria-expanded",
    "false",
  );
});

it("archiving AC40: lines without a category are named and hold their products", async () => {
  answerArchiveTotals();
  const user = userEvent.setup();
  render(<ArchiveYearPage year={2025} />);
  await screen.findByRole("table", { name: "Vuosi 2025" });

  await user.click(screen.getByRole("button", { name: "Näytä tuotteet: Ei kategoriaa" }));

  expect(row("TUNTEMATON")).toBeInTheDocument();
});

it("archiving AC41: a year that is not archived says so", async () => {
  answerArchiveTotals();
  render(<ArchiveYearPage year={2023} />);

  expect(await screen.findByText("Vuotta 2023 ei ole arkistossa.")).toBeInTheDocument();
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Vie CSV" })).not.toBeInTheDocument();
});

it("archiving AC43: the wide box, the sticky name column and wrapping names", async () => {
  answerArchiveTotals();
  render(<ArchiveYearPage year={2025} />);
  await screen.findByRole("table", { name: "Vuosi 2025" });

  expect(table().parentElement).toHaveClass("table-box", "table-box-wide");
  expect(table()).toHaveClass("archive-table");
  for (const header of within(table()).getAllByRole("rowheader")) {
    expect(header).toHaveClass("archive-name");
  }
});
