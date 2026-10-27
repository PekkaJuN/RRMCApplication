import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { defaultItems, itemNamed } from "../test/catalog";
import { CategorySelect } from "./CategorySelect";

const items = defaultItems();

describe("CategorySelect", () => {
  it("AC29: lists the 21 categories, with groups only as headings", () => {
    render(<CategorySelect label="Kategoria" items={items} value={null} onChange={() => {}} />);

    const select = screen.getByRole("combobox", { name: "Kategoria" });
    const options = within(select)
      .getAllByRole("option")
      .filter((option) => !(option as HTMLOptionElement).disabled);
    expect(options).toHaveLength(21);
    expect(options.map((option) => option.textContent)).not.toContain("Ruoka");
    const groups = [...select.querySelectorAll("optgroup")].map((group) => group.label);
    expect(groups).toEqual(["Auto", "Ruoka"]);
    expect(
      within(select.querySelectorAll("optgroup")[1] as HTMLElement).getAllByRole("option"),
    ).toHaveLength(10);
  });

  it("AC29: categories without a group come after the groups", () => {
    render(<CategorySelect label="Kategoria" items={items} value={null} onChange={() => {}} />);

    const select = screen.getByRole("combobox", { name: "Kategoria" });
    const ungrouped = [...select.children]
      .filter((child) => child.tagName === "OPTION" && !(child as HTMLOptionElement).disabled)
      .map((option) => option.textContent);
    expect(ungrouped[0]).toBe("Alkoholi");
    expect(select.lastElementChild?.textContent).toBe("Ulkona syöminen");
  });

  it("AC20: choosing a category reports its id", async () => {
    const onChange = vi.fn();
    render(<CategorySelect label="Kategoria" items={items} value={null} onChange={onChange} />);

    await userEvent.selectOptions(screen.getByRole("combobox", { name: "Kategoria" }), "Juomat");

    expect(onChange).toHaveBeenCalledWith(itemNamed(items, "Juomat").id);
  });

  it("AC24: the filter variant offers all products and whole groups", async () => {
    const onChange = vi.fn();
    render(
      <CategorySelect label="Suodata" items={items} value={null} onChange={onChange} isFilter />,
    );
    const select = screen.getByRole("combobox", { name: "Suodata" });

    expect(within(select).getByRole("option", { name: "Kaikki" })).toBeInTheDocument();
    await userEvent.selectOptions(select, "Ruoka (koko ryhmä)");
    expect(onChange).toHaveBeenLastCalledWith(itemNamed(items, "Ruoka").id);
    await userEvent.selectOptions(select, "Kaikki");
    expect(onChange).toHaveBeenLastCalledWith(null);
  });
});
