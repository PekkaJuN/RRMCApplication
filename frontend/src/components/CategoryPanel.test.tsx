import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { useCallback, useEffect, useState } from "react";
import { beforeEach, describe, expect, it } from "vitest";
import { listCategories, type CatalogItem } from "../api/catalog";
import { defaultItems, fakeCatalog } from "../test/catalog";
import { server } from "../test/server";
import { CategoryPanel } from "./CategoryPanel";

type CatalogState = ReturnType<typeof fakeCatalog>;

/** Loads the categories and reloads them after a change, and keeps the selection, as the page does. */
function Harness({ initialSelectedId = null }: { initialSelectedId?: number | null }) {
  const [items, setItems] = useState<CatalogItem[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(initialSelectedId);
  const reload = useCallback(() => {
    void listCategories().then((result) => {
      if (result.ok) {
        setItems(result.data);
      }
    });
  }, []);
  useEffect(reload, [reload]);
  return (
    <CategoryPanel
      items={items}
      selectedId={selectedId}
      onSelect={setSelectedId}
      onChanged={reload}
    />
  );
}

function column(): HTMLElement {
  return screen.getByRole("region", { name: "Kategoriat" });
}

/** The selectable buttons of the tree, in order. */
function treeItems(): HTMLElement[] {
  return within(column())
    .getAllByRole("button")
    .filter((button) => button.hasAttribute("aria-pressed"));
}

function treeItem(name: string): HTMLElement {
  const item = treeItems().find((button) => button.textContent === name);
  if (!item) {
    throw new Error(`No tree item ${name}`);
  }
  return item;
}

/** The text after the tree item, its count. */
function countOf(name: string): string | null | undefined {
  return treeItem(name).closest("li")?.querySelector("[data-count]")?.textContent;
}

function groupOf(name: string): string | null {
  const group = treeItem(name).closest("li")?.parentElement?.closest("li");
  return group?.querySelector("[aria-pressed]")?.textContent ?? null;
}

async function loaded(): Promise<void> {
  await within(column()).findByRole("button", { name: "Ruoka" });
}

const DEFAULT_NAMES = defaultItems().map((item) => item.name);

function idOf(name: string): number {
  const item = defaultItems().find((candidate) => candidate.name === name);
  if (!item) {
    throw new Error(`No test item ${name}`);
  }
  return item.id;
}

let state: CatalogState;

beforeEach(() => {
  state = fakeCatalog(server);
});

describe("CategoryPanel", () => {
  // Changed from list items with controls to the tree (product management AC1, G7 record).
  it("AC1: the tree has Kaikki tuotteet, the groups with their categories, then the categories without a group", async () => {
    render(<Harness />);
    await loaded();

    expect(screen.getByRole("heading", { name: "Kategoriat" })).toBeInTheDocument();
    expect(treeItems().map((item) => item.textContent)).toEqual([
      "Kaikki tuotteet",
      ...DEFAULT_NAMES,
    ]);
    expect(countOf("Ruoka")).toBe("10 kategoriaa");
    expect(countOf("Auto")).toBe("3 kategoriaa");
    expect(countOf("Juomat")).toBe("0 tuotetta");
    expect(groupOf("Pakasteet")).toBe("Ruoka");
    expect(groupOf("Autohuolto")).toBe("Auto");
    expect(groupOf("Juomat")).toBeNull();
    for (const name of ["Nimeä", "Muuta ryhmäksi", "Muuta kategoriaksi", "Poista"]) {
      expect(within(column()).queryByRole("button", { name })).not.toBeInTheDocument();
    }
  });

  it("AC1, AC2: Kaikki tuotteet is pressed first, and a click selects another item", async () => {
    render(<Harness />);
    await loaded();

    expect(treeItem("Kaikki tuotteet")).toHaveAttribute("aria-pressed", "true");
    expect(treeItem("Leivät")).toHaveAttribute("aria-pressed", "false");

    await userEvent.click(treeItem("Leivät"));

    expect(treeItem("Leivät")).toHaveAttribute("aria-pressed", "true");
    expect(treeItem("Kaikki tuotteet")).toHaveAttribute("aria-pressed", "false");
    expect(treeItems().filter((item) => item.getAttribute("aria-pressed") === "true")).toHaveLength(
      1,
    );

    await userEvent.click(treeItem("Kaikki tuotteet"));
    expect(treeItem("Kaikki tuotteet")).toHaveAttribute("aria-pressed", "true");
  });

  it("AC5: a group closes and opens", async () => {
    render(<Harness />);
    await loaded();

    const toggle = within(column()).getByRole("button", { name: "Piilota kategoriat: Ruoka" });
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    const list = document.getElementById(toggle.getAttribute("aria-controls") ?? "");
    expect(list).not.toBeNull();
    expect(within(list as HTMLElement).getByRole("button", { name: "Leivät" })).toBeVisible();

    await userEvent.click(toggle);

    expect(toggle).toHaveAccessibleName("Näytä kategoriat: Ruoka");
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    const names = treeItems().map((item) => item.textContent);
    expect(names).not.toContain("Leivät");
    expect(names).not.toContain("Pakasteet");
    expect(names).toContain("Autohuolto");
    expect(names).toContain("Juomat");

    await userEvent.click(toggle);

    expect(toggle).toHaveAccessibleName("Piilota kategoriat: Ruoka");
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(treeItems().map((item) => item.textContent)).toEqual([
      "Kaikki tuotteet",
      ...DEFAULT_NAMES,
    ]);
  });

  it("AC6: closing a group keeps the selected category", async () => {
    render(<Harness initialSelectedId={idOf("Leivät")} />);
    await loaded();

    await userEvent.click(
      within(column()).getByRole("button", { name: "Piilota kategoriat: Ruoka" }),
    );

    expect(treeItem("Kaikki tuotteet")).toHaveAttribute("aria-pressed", "false");
  });

  it("AC7: a group without categories has no toggle", async () => {
    const koti: CatalogItem = {
      id: 500,
      name: "Koti",
      kind: "group",
      parent_id: null,
      product_count: null,
      category_count: 0,
    };
    state = fakeCatalog(server, [...defaultItems(), koti]);
    render(<Harness />);
    await loaded();

    expect(countOf("Koti")).toBe("0 kategoriaa");
    expect(
      within(column()).queryByRole("button", { name: /kategoriat: Koti$/ }),
    ).not.toBeInTheDocument();
  });

  it("AC15: the add forms open from their buttons, one at a time", async () => {
    render(<Harness />);
    await loaded();

    const newGroup = within(column()).getByRole("button", { name: "Uusi ryhmä" });
    const newCategory = within(column()).getByRole("button", { name: "Uusi kategoria" });
    expect(screen.queryByRole("form", { name: "Uusi ryhmä" })).not.toBeInTheDocument();
    expect(screen.queryByRole("form", { name: "Uusi kategoria" })).not.toBeInTheDocument();
    expect(newGroup).toHaveAttribute("aria-expanded", "false");
    expect(newCategory).toHaveAttribute("aria-expanded", "false");

    await userEvent.click(newGroup);

    const groupForm = screen.getByRole("form", { name: "Uusi ryhmä" });
    expect(newGroup).toHaveAttribute("aria-expanded", "true");
    expect(newGroup).toHaveAttribute("aria-controls", groupForm.id);
    const name = within(groupForm).getByRole("textbox", { name: "Ryhmän nimi" });
    expect(name).toHaveFocus();

    await userEvent.type(name, "Koti");
    await userEvent.click(within(groupForm).getByRole("button", { name: "Lisää" }));

    expect(await within(column()).findByRole("button", { name: "Koti" })).toBeInTheDocument();
    expect(name).toHaveValue("");
    expect(screen.getByRole("form", { name: "Uusi ryhmä" })).toBeInTheDocument();

    await userEvent.click(newCategory);

    const categoryForm = screen.getByRole("form", { name: "Uusi kategoria" });
    expect(newCategory).toHaveAttribute("aria-controls", categoryForm.id);
    expect(screen.queryByRole("form", { name: "Uusi ryhmä" })).not.toBeInTheDocument();
    expect(newGroup).toHaveAttribute("aria-expanded", "false");

    await userEvent.click(newCategory);

    expect(screen.queryByRole("form", { name: "Uusi kategoria" })).not.toBeInTheDocument();
    expect(newCategory).toHaveAttribute("aria-expanded", "false");
  });

  it("AC16: Peruuta closes a form and sends nothing", async () => {
    render(<Harness />);
    await loaded();
    const newCategory = within(column()).getByRole("button", { name: "Uusi kategoria" });
    await userEvent.click(newCategory);
    const form = screen.getByRole("form", { name: "Uusi kategoria" });
    await userEvent.type(within(form).getByRole("textbox", { name: "Kategorian nimi" }), "Kahvi");
    const requests: string[] = [];
    const record = ({ request }: { request: Request }) => {
      requests.push(request.method);
    };
    server.events.on("request:start", record);

    await userEvent.click(within(form).getByRole("button", { name: "Peruuta" }));

    server.events.removeListener("request:start", record);
    expect(requests).toEqual([]);
    expect(screen.queryByRole("form", { name: "Uusi kategoria" })).not.toBeInTheDocument();
    expect(newCategory).toHaveAttribute("aria-expanded", "false");
  });

  it("AC16: Peruuta closes the new group form too", async () => {
    render(<Harness />);
    await loaded();
    const newGroup = within(column()).getByRole("button", { name: "Uusi ryhmä" });
    await userEvent.click(newGroup);

    await userEvent.click(
      within(screen.getByRole("form", { name: "Uusi ryhmä" })).getByRole("button", {
        name: "Peruuta",
      }),
    );

    expect(screen.queryByRole("form", { name: "Uusi ryhmä" })).not.toBeInTheDocument();
    expect(newGroup).toHaveAttribute("aria-expanded", "false");
  });

  it.each([
    ["Leivät", "Ruoka"],
    ["Ruoka", "Ruoka"],
    ["Juomat", "Ei ryhmää"],
  ])("AC17: with %s selected, the new category's group starts at %s", async (selected, group) => {
    render(<Harness initialSelectedId={idOf(selected)} />);
    await loaded();

    await userEvent.click(within(column()).getByRole("button", { name: "Uusi kategoria" }));

    const form = screen.getByRole("form", { name: "Uusi kategoria" });
    expect(within(form).getByRole("combobox", { name: "Ryhmä" })).toHaveDisplayValue(group);
  });

  it("AC17: with Kaikki tuotteet selected the group starts at Ei ryhmää; a category added with Leivät selected goes to Ruoka", async () => {
    render(<Harness />);
    await loaded();
    await userEvent.click(within(column()).getByRole("button", { name: "Uusi kategoria" }));
    const form = screen.getByRole("form", { name: "Uusi kategoria" });
    expect(within(form).getByRole("combobox", { name: "Ryhmä" })).toHaveDisplayValue("Ei ryhmää");

    await userEvent.click(within(column()).getByRole("button", { name: "Uusi kategoria" }));
    await userEvent.click(treeItem("Leivät"));
    await userEvent.click(within(column()).getByRole("button", { name: "Uusi kategoria" }));
    const reopened = screen.getByRole("form", { name: "Uusi kategoria" });
    await userEvent.type(
      within(reopened).getByRole("textbox", { name: "Kategorian nimi" }),
      "Kahvi",
    );
    await userEvent.click(within(reopened).getByRole("button", { name: "Lisää" }));

    expect(await within(column()).findByRole("button", { name: "Kahvi" })).toBeInTheDocument();
    expect(groupOf("Kahvi")).toBe("Ruoka");
    expect(state.items.find((item) => item.name === "Kahvi")?.parent_id).toBe(idOf("Ruoka"));
  });

  // Moved from the always-shown forms to the forms behind buttons (product management AC8, G7 record).
  it("product management AC8: adds a group and a category in it", async () => {
    render(<Harness />);
    await loaded();

    await userEvent.click(within(column()).getByRole("button", { name: "Uusi ryhmä" }));
    const groupForm = screen.getByRole("form", { name: "Uusi ryhmä" });
    await userEvent.type(within(groupForm).getByRole("textbox", { name: "Ryhmän nimi" }), "Koti");
    await userEvent.click(within(groupForm).getByRole("button", { name: "Lisää" }));
    await within(column()).findByRole("button", { name: "Koti" });
    await userEvent.click(within(column()).getByRole("button", { name: "Uusi kategoria" }));
    const categoryForm = screen.getByRole("form", { name: "Uusi kategoria" });
    await userEvent.type(
      within(categoryForm).getByRole("textbox", { name: "Kategorian nimi" }),
      "Sisustus",
    );
    await userEvent.selectOptions(
      within(categoryForm).getByRole("combobox", { name: "Ryhmä" }),
      "Koti",
    );
    await userEvent.click(within(categoryForm).getByRole("button", { name: "Lisää" }));

    await within(column()).findByRole("button", { name: "Sisustus" });
    expect(groupOf("Sisustus")).toBe("Koti");
  });

  // Moved from the always-shown forms to the forms behind buttons (product management AC5, AC27, G7 record).
  it("product management AC5, AC27: a refused new name is shown next to the add form", async () => {
    server.use(
      http.post("/api/categories", () =>
        HttpResponse.json(
          { error: "duplicate_name", message: "Samanniminen ryhmä tai kategoria on jo olemassa." },
          { status: 409 },
        ),
      ),
    );
    render(<Harness />);
    await loaded();

    await userEvent.click(within(column()).getByRole("button", { name: "Uusi ryhmä" }));
    const groupForm = screen.getByRole("form", { name: "Uusi ryhmä" });
    await userEvent.type(within(groupForm).getByRole("textbox", { name: "Ryhmän nimi" }), "ruoka");
    await userEvent.click(within(groupForm).getByRole("button", { name: "Lisää" }));

    expect(await within(groupForm).findByRole("alert")).toHaveTextContent(
      "Samanniminen ryhmä tai kategoria on jo olemassa.",
    );
  });
});
