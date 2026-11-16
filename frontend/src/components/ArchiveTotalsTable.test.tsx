import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it } from "vitest";
import type { YearTotals } from "../api/totals";
import { YEAR_TOTALS } from "../test/year";
import { ArchiveTotalsTable } from "./ArchiveTotalsTable";

// Expand and collapse a whole level (specs/features/table-expand-all.md), AC1–AC8.

const table = () => screen.getByRole("table", { name: "Vuosi 2026" });

/** The names of the body rows shown, in order. */
function rowsShown(): string[] {
  const body = table().querySelector("tbody") as HTMLElement;
  return within(body)
    .getAllByRole("rowheader")
    .map((cell) => cell.querySelector("span")?.textContent ?? "");
}

/** The level buttons above the table, in order: their text and `aria-expanded`. */
function levelButtons(): [string, string | null][] {
  const box = table().parentElement as HTMLElement;
  return screen
    .getAllByRole("button")
    .filter((button) => !box.contains(button))
    .map((button) => [button.textContent ?? "", button.getAttribute("aria-expanded")]);
}

const button = (name: string) => screen.getByRole("button", { name });

const OPENING = ["Kahvi", "Maitotuotteet", "Juusto", "Maito", "Ei kategoriaa"];
const ALL = [
  "Kahvi",
  "Kahvi 500g",
  "Maitotuotteet",
  "Juusto",
  "Edam",
  "Maito",
  "Maito 1l",
  "Ei kategoriaa",
  "TUNTEMATON",
];

function setup(totals: YearTotals = YEAR_TOTALS) {
  const user = userEvent.setup();
  render(<ArchiveTotalsTable totals={totals} />);
  return user;
}

it("table-expand-all AC1: two level buttons above the table on opening", () => {
  setup();

  expect(levelButtons()).toEqual([
    ["Piilota kategoriat", "true"],
    ["Näytä tuotteet", "false"],
  ]);
  const id = table().id;
  expect(id).not.toBe("");
  expect(button("Piilota kategoriat")).toHaveAttribute("aria-controls", id);
  expect(button("Näytä tuotteet")).toHaveAttribute("aria-controls", id);
  expect(rowsShown()).toEqual(OPENING);
});

it("table-expand-all AC2: Näytä tuotteet shows every row", async () => {
  const user = setup();

  await user.click(button("Näytä tuotteet"));

  expect(rowsShown()).toEqual(ALL);
  expect(levelButtons()).toEqual([
    ["Piilota kategoriat", "true"],
    ["Piilota tuotteet", "true"],
  ]);
  for (const toggle of within(table()).getAllByRole("button")) {
    expect(toggle).toHaveAttribute("aria-expanded", "true");
  }
});

it("table-expand-all AC3: Piilota kategoriat leaves the top level only", async () => {
  const user = setup();
  await user.click(button("Näytä tuotteet"));

  await user.click(button("Piilota kategoriat"));

  expect(rowsShown()).toEqual(["Kahvi", "Maitotuotteet", "Ei kategoriaa"]);
  const total = within(table()).getByRole("row", { name: /^Yhteensä/ });
  expect(within(total).getAllByRole("cell").at(-1)).toHaveTextContent("15,00 €");
  expect(levelButtons()).toEqual([
    ["Näytä kategoriat", "false"],
    ["Näytä tuotteet", "false"],
  ]);
});

it("table-expand-all AC4: Näytä kategoriat returns to the opening view", async () => {
  const user = setup();
  await user.click(button("Näytä tuotteet"));
  await user.click(button("Piilota kategoriat"));

  await user.click(button("Näytä kategoriat"));

  expect(rowsShown()).toEqual(OPENING);
  expect(levelButtons()).toEqual([
    ["Piilota kategoriat", "true"],
    ["Näytä tuotteet", "false"],
  ]);
});

it("table-expand-all AC5: Piilota tuotteet closes the categories", async () => {
  const user = setup();
  await user.click(button("Näytä tuotteet"));

  await user.click(button("Piilota tuotteet"));

  expect(rowsShown()).toEqual(OPENING);
  expect(levelButtons()).toEqual([
    ["Piilota kategoriat", "true"],
    ["Näytä tuotteet", "false"],
  ]);
});

it("table-expand-all AC6: the level buttons follow the row toggles", async () => {
  const user = setup();

  for (const name of ["Kahvi", "Juusto", "Maito", "Ei kategoriaa"]) {
    await user.click(button(`Näytä tuotteet: ${name}`));
  }
  expect(levelButtons()).toEqual([
    ["Piilota kategoriat", "true"],
    ["Piilota tuotteet", "true"],
  ]);

  await user.click(button("Piilota kategoriat: Maitotuotteet"));

  expect(levelButtons()).toEqual([
    ["Näytä kategoriat", "false"],
    ["Näytä tuotteet", "false"],
  ]);
  expect(rowsShown()).toEqual([
    "Kahvi",
    "Kahvi 500g",
    "Maitotuotteet",
    "Ei kategoriaa",
    "TUNTEMATON",
  ]);
});

it("table-expand-all AC7: Näytä kategoriat keeps the open categories open", async () => {
  const user = setup();
  await user.click(button("Näytä tuotteet"));
  await user.click(button("Piilota kategoriat: Maitotuotteet"));

  await user.click(button("Näytä kategoriat"));

  expect(rowsShown()).toEqual(ALL);
});

it("table-expand-all AC8: without groups only the products button shows", async () => {
  const rows = YEAR_TOTALS.rows.filter((row) => row.kind !== "group");
  const user = setup({ ...YEAR_TOTALS, rows });

  expect(levelButtons()).toEqual([["Näytä tuotteet", "false"]]);

  await user.click(button("Näytä tuotteet"));

  expect(rowsShown()).toEqual(["Kahvi", "Kahvi 500g", "Ei kategoriaa", "TUNTEMATON"]);
});
