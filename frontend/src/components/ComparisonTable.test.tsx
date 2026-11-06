import { render, screen, within } from "@testing-library/react";
import { expect, it } from "vitest";
import type { Comparison } from "../api/budget";
import { OCTOBER_COMPARISON } from "../test/budget";
import { ComparisonMonthTable, ComparisonWeekTable } from "./ComparisonTable";

function monthRow(name: RegExp): HTMLElement {
  return within(screen.getByRole("table", { name: "Kuukausi" })).getByRole("row", { name });
}

function weekRow(name: RegExp): HTMLElement {
  return within(screen.getByRole("table", { name: "Viikot" })).getByRole("row", { name });
}

it("budget PC6: the month table has its columns and the total row", () => {
  render(<ComparisonMonthTable comparison={OCTOBER_COMPARISON} />);

  const table = screen.getByRole("table", { name: "Kuukausi" });
  const headers = within(table).getAllByRole("columnheader");
  expect(headers.map((header) => header.textContent)).toEqual([
    "Kategoria",
    "Budjetti",
    "Toteutunut",
    "Jäljellä",
  ]);
  expect(monthRow(/Ruoka/)).toHaveTextContent("400,00 €125,00 €275,00 €");
  expect(monthRow(/Yhteensä/)).toHaveTextContent("450,00 €176,00 €274,00 €");
});

it("budget AC8: a negative remaining has the text as well as the sign", () => {
  render(<ComparisonMonthTable comparison={OCTOBER_COMPARISON} />);

  expect(within(monthRow(/Juomat/)).getByText(/-1,00 €/)).toHaveTextContent("Ylitetty");
  expect(monthRow(/Ruoka/)).not.toHaveTextContent("Ylitetty");
});

it("budget AC13: the row without a category has its name", () => {
  const comparison: Comparison = {
    ...OCTOBER_COMPARISON,
    rows: [
      ...OCTOBER_COMPARISON.rows,
      {
        kind: "none",
        id: null,
        name: null,
        budget_cents: 0,
        actual_cents: 199,
        remaining_cents: -199,
        weeks: [
          { budget_cents: 0, actual_cents: 199 },
          { budget_cents: 0, actual_cents: 0 },
        ],
      },
    ],
  };
  render(<ComparisonMonthTable comparison={comparison} />);

  expect(monthRow(/Ei kategoriaa/)).toHaveTextContent("-1,99 € Ylitetty");
});

it("budget PC6: the week table has two heading rows", () => {
  render(<ComparisonWeekTable comparison={OCTOBER_COMPARISON} />);

  const table = screen.getByRole("table", { name: "Viikot" });
  const [groups, columns] = within(table).getAllByRole("row");
  expect(groups).toHaveTextContent("vk 41/2026");
  const names = within(columns as HTMLElement)
    .getAllByRole("columnheader")
    .map((header) => header.textContent);
  expect(names).toEqual(["Budjetti", "Toteutunut", "Budjetti", "Toteutunut"]);
});

it("budget PC10: a partial week shows the mark and its days", () => {
  render(<ComparisonWeekTable comparison={OCTOBER_COMPARISON} />);

  expect(
    screen.getByRole("columnheader", { name: "vk 40/2026 (osittainen) 1.10.–4.10.2026" }),
  ).toBeInTheDocument();
});

it("budget AC8: a week over its budget has the text; one equal to it does not", () => {
  render(<ComparisonWeekTable comparison={OCTOBER_COMPARISON} />);

  const row = weekRow(/Juomat/);
  expect(within(row).getByText(/51,00 €/)).toHaveTextContent("Ylitetty");
  const equal = within(row).getAllByText(/11,29 €/);
  expect(equal).toHaveLength(2);
  equal.forEach((cell) => expect(cell).not.toHaveTextContent("Ylitetty"));
});

it("budget PC6: the week table has the total row", () => {
  render(<ComparisonWeekTable comparison={OCTOBER_COMPARISON} />);

  expect(weekRow(/Yhteensä/)).toHaveTextContent("58,06 €176,00 € Ylitetty101,61 €11,29 €");
});
