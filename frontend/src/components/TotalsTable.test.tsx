import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { expect, it } from "vitest";
import type { TotalsColumn } from "../api/totals";
import { OCTOBER } from "../test/totals";
import { TotalsTable } from "./TotalsTable";

function Weeks({ columns = OCTOBER.weeks }: { columns?: TotalsColumn[] }) {
  const [expanded, setExpanded] = useState<ReadonlySet<number>>(new Set());
  return (
    <TotalsTable
      label="Viikot"
      unit="week"
      columns={columns}
      rows={OCTOBER.rows}
      totals={OCTOBER.week_totals}
      expanded={expanded}
      onToggle={(id) => {
        const next = new Set(expanded);
        if (!next.delete(id)) {
          next.add(id);
        }
        setExpanded(next);
      }}
    />
  );
}

function rowTexts(): string[][] {
  const table = screen.getByRole("table", { name: "Viikot" });
  return within(table)
    .getAllByRole("row")
    .map((row) => Array.from(row.querySelectorAll("th, td"), (cell) => cell.textContent ?? ""));
}

it("totals AC17: a partial column's heading has the mark and its days", () => {
  render(<Weeks />);

  const headings = within(screen.getByRole("table", { name: "Viikot" })).getAllByRole(
    "columnheader",
  );
  expect(headings.map((heading) => heading.textContent)).toEqual([
    "Kategoria",
    "vk 40/2026 (osittainen) 1.10.–4.10.2026",
    "vk 41/2026",
  ]);
});

it("totals AC23: month and week labels without leading zeros", () => {
  render(
    <TotalsTable
      label="Kuukaudet"
      unit="month"
      columns={[
        { key: "2026-12", start_date: "2026-12-28", end_date: "2026-12-31", partial: true },
        { key: "2027-01", start_date: "2027-01-01", end_date: "2027-01-03", partial: true },
      ]}
      rows={[]}
      totals={[0, 0]}
      expanded={new Set()}
      onToggle={() => undefined}
    />,
  );
  render(
    <Weeks
      columns={[
        { key: "2027-W01", start_date: "2027-01-04", end_date: "2027-01-10", partial: false },
        { key: "2027-W02", start_date: "2027-01-11", end_date: "2027-01-17", partial: false },
      ]}
    />,
  );

  const months = screen.getByRole("table", { name: "Kuukaudet" });
  expect(
    within(months)
      .getAllByRole("columnheader")
      .map((cell) => cell.textContent),
  ).toEqual([
    "Kategoria",
    "12/2026 (osittainen) 28.12.–31.12.2026",
    "1/2027 (osittainen) 1.1.–3.1.2027",
  ]);
  const weeks = screen.getByRole("table", { name: "Viikot" });
  expect(within(weeks).getAllByRole("columnheader")[1]).toHaveTextContent("vk 1/2027");
});

it("totals AC14: rows show groups, categories without a group, no category and the total", () => {
  render(<Weeks />);

  expect(rowTexts()).toEqual([
    ["Kategoria", "vk 40/2026 (osittainen) 1.10.–4.10.2026", "vk 41/2026"],
    ["+ Ruoka", "1,25 €", "3,00 €"],
    ["Juomat", "0,00 €", "1234,56 €"],
    ["Ei kategoriaa", "0,00 €", "1,99 €"],
    ["Yhteensä", "1,25 €", "1239,55 €"],
  ]);
});

it("totals AC15: a group expands to show its categories and collapses again", async () => {
  const user = userEvent.setup();
  render(<Weeks />);

  const expand = screen.getByRole("button", { name: "Näytä kategoriat: Ruoka" });
  expect(expand).toHaveAttribute("aria-expanded", "false");
  await user.click(expand);

  const collapse = screen.getByRole("button", { name: "Piilota kategoriat: Ruoka" });
  expect(collapse).toHaveAttribute("aria-expanded", "true");
  expect(rowTexts().slice(1, 4)).toEqual([
    ["− Ruoka", "1,25 €", "3,00 €"],
    ["Leivät", "0,00 €", "3,00 €"],
    ["Maitotuotteet", "1,25 €", "0,00 €"],
  ]);

  await user.click(collapse);

  expect(rowTexts()).toHaveLength(5);
  expect(screen.getByRole("button", { name: "Näytä kategoriat: Ruoka" })).toBeInTheDocument();
});

it("styling AC1: an expanded totals table has no inline style", async () => {
  const user = userEvent.setup();
  const { container } = render(<Weeks />);

  await user.click(screen.getByRole("button", { name: "Näytä kategoriat: Ruoka" }));

  expect(screen.getByRole("rowheader", { name: "Leivät" })).toBeInTheDocument();
  expect(container.querySelectorAll("[style]")).toHaveLength(0);
});
