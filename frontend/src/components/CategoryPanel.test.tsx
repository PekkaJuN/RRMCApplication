import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { useCallback, useEffect, useState } from "react";
import { beforeEach, describe, expect, it } from "vitest";
import { listCategories, type CatalogItem } from "../api/catalog";
import { fakeCatalog } from "../test/catalog";
import { server } from "../test/server";
import { CategoryPanel } from "./CategoryPanel";

/** Loads the categories and reloads them after a change, as the page does. */
function Harness() {
  const [items, setItems] = useState<CatalogItem[]>([]);
  const reload = useCallback(() => {
    void listCategories().then((result) => {
      if (result.ok) {
        setItems(result.data);
      }
    });
  }, []);
  useEffect(reload, [reload]);
  return <CategoryPanel items={items} onChanged={reload} />;
}

/** The list item of a group or category, found by its name. */
async function entry(name: string): Promise<HTMLElement> {
  const label = await screen.findByText(name, { selector: "[data-name]" });
  const item = label.closest("li");
  if (!item) {
    throw new Error(`No list item for ${name}`);
  }
  return item;
}

function groupOf(name: string): string | null {
  const item = screen.getByText(name, { selector: "[data-name]" }).closest("li");
  const group = item?.parentElement?.closest("li");
  return group?.querySelector("[data-name]")?.textContent ?? null;
}

beforeEach(() => {
  fakeCatalog(server);
});

describe("CategoryPanel", () => {
  it("AC1: shows the groups with their categories, then the categories without a group", async () => {
    render(<Harness />);

    expect(await screen.findByRole("heading", { name: "Kategoriat" })).toBeInTheDocument();
    expect(within(await entry("Ruoka")).getByText("10 kategoriaa")).toBeInTheDocument();
    expect(groupOf("Pakasteet")).toBe("Ruoka");
    expect(groupOf("Autohuolto")).toBe("Auto");
    expect(groupOf("Juomat")).toBeNull();
    expect(within(await entry("Juomat")).getByText("0 tuotetta")).toBeInTheDocument();
  });

  it("AC9: moves a category out of its group", async () => {
    render(<Harness />);

    await userEvent.selectOptions(
      within(await entry("Pakasteet")).getByRole("combobox", { name: "Ryhmä: Pakasteet" }),
      "Ei ryhmää",
    );

    expect(await within(await entry("Ruoka")).findByText("9 kategoriaa")).toBeInTheDocument();
    expect(groupOf("Pakasteet")).toBeNull();
  });

  it("AC8: adds a group and a category in it", async () => {
    render(<Harness />);
    await entry("Ruoka");

    const groupForm = screen.getByRole("form", { name: "Uusi ryhmä" });
    await userEvent.type(within(groupForm).getByRole("textbox", { name: "Ryhmän nimi" }), "Koti");
    await userEvent.click(within(groupForm).getByRole("button", { name: "Lisää" }));
    await entry("Koti");
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

    await entry("Sisustus");
    expect(groupOf("Sisustus")).toBe("Koti");
    expect(within(groupForm).getByRole("textbox", { name: "Ryhmän nimi" })).toHaveValue("");
  });

  it("AC5, AC27: a refused new name is shown next to the add form", async () => {
    server.use(
      http.post("/api/categories", () =>
        HttpResponse.json(
          { error: "duplicate_name", message: "Samanniminen ryhmä tai kategoria on jo olemassa." },
          { status: 409 },
        ),
      ),
    );
    render(<Harness />);
    await entry("Ruoka");

    const groupForm = screen.getByRole("form", { name: "Uusi ryhmä" });
    await userEvent.type(within(groupForm).getByRole("textbox", { name: "Ryhmän nimi" }), "ruoka");
    await userEvent.click(within(groupForm).getByRole("button", { name: "Lisää" }));

    expect(await within(groupForm).findByRole("alert")).toHaveTextContent(
      "Samanniminen ryhmä tai kategoria on jo olemassa.",
    );
  });

  it("AC6: renames a category", async () => {
    render(<Harness />);

    const juomat = await entry("Juomat");
    await userEvent.click(within(juomat).getByRole("button", { name: "Nimeä" }));
    const input = within(juomat).getByRole("textbox", { name: "Kategorian nimi" });
    await userEvent.clear(input);
    await userEvent.type(input, "Virvoitusjuomat");
    await userEvent.click(within(juomat).getByRole("button", { name: "Tallenna" }));

    expect(await entry("Virvoitusjuomat")).toBeInTheDocument();
  });

  it("AC11: converts an empty group into a category", async () => {
    render(<Harness />);
    await entry("Ruoka");
    const groupForm = screen.getByRole("form", { name: "Uusi ryhmä" });
    await userEvent.type(within(groupForm).getByRole("textbox", { name: "Ryhmän nimi" }), "Koti");
    await userEvent.click(within(groupForm).getByRole("button", { name: "Lisää" }));

    await userEvent.click(
      within(await entry("Koti")).getByRole("button", { name: "Muuta kategoriaksi" }),
    );

    expect(
      await within(await entry("Koti")).findByRole("button", { name: "Muuta ryhmäksi" }),
    ).toBeInTheDocument();
  });

  it("AC12, AC27: a refused conversion shows the message next to the category", async () => {
    server.use(
      http.patch("/api/categories/:id", () =>
        HttpResponse.json(
          {
            error: "category_has_products",
            message: "Kategoriaa, jossa on tuotteita, ei voi muuttaa ryhmäksi.",
          },
          { status: 409 },
        ),
      ),
    );
    render(<Harness />);

    const juomat = await entry("Juomat");
    await userEvent.click(within(juomat).getByRole("button", { name: "Muuta ryhmäksi" }));

    expect(await within(juomat).findByRole("alert")).toHaveTextContent(
      "Kategoriaa, jossa on tuotteita, ei voi muuttaa ryhmäksi.",
    );
    expect(groupOf("Juomat")).toBeNull();
  });

  it("AC13, AC27: a category in use is not deleted and tells the count", async () => {
    server.use(
      http.delete("/api/categories/:id", () =>
        HttpResponse.json(
          { error: "category_in_use", message: "Kategoriaa käyttää 3 tuotetta.", product_count: 3 },
          { status: 409 },
        ),
      ),
    );
    render(<Harness />);

    const juomat = await entry("Juomat");
    await userEvent.click(within(juomat).getByRole("button", { name: "Poista" }));
    await userEvent.click(within(juomat).getByRole("button", { name: "Poista" }));

    expect(await within(juomat).findByRole("alert")).toHaveTextContent(
      "Kategoriaa käyttää 3 tuotetta.",
    );
    expect(await entry("Juomat")).toBeInTheDocument();
  });

  it("AC14: a group with categories is not deleted", async () => {
    server.use(
      http.delete("/api/categories/:id", () =>
        HttpResponse.json(
          { error: "group_not_empty", message: "Ryhmässä on 3 kategoriaa.", category_count: 3 },
          { status: 409 },
        ),
      ),
    );
    render(<Harness />);

    // The group's own delete button comes before those of its categories.
    const auto = await entry("Auto");
    const [askDelete] = within(auto).getAllByRole("button", { name: "Poista" });
    await userEvent.click(askDelete as HTMLElement);
    const [confirmDelete] = within(auto).getAllByRole("button", { name: "Poista" });
    await userEvent.click(confirmDelete as HTMLElement);

    expect(await within(auto).findByRole("alert")).toHaveTextContent("Ryhmässä on 3 kategoriaa.");
    expect(groupOf("Autohuolto")).toBe("Auto");
  });

  it("AC28: cancelling a category delete sends no request", async () => {
    render(<Harness />);
    const juomat = await entry("Juomat");
    const requests: string[] = [];
    const record = ({ request }: { request: Request }) => {
      requests.push(request.method);
    };
    server.events.on("request:start", record);

    await userEvent.click(within(juomat).getByRole("button", { name: "Poista" }));
    await userEvent.click(within(juomat).getByRole("button", { name: "Peruuta" }));

    server.events.removeListener("request:start", record);
    expect(requests).toEqual([]);
    expect(await entry("Juomat")).toBeInTheDocument();
  });

  it("AC15: deletes an unused category after confirmation", async () => {
    render(<Harness />);

    const muut = await entry("Muut");
    await userEvent.click(within(muut).getByRole("button", { name: "Poista" }));
    await userEvent.click(within(muut).getByRole("button", { name: "Poista" }));

    await screen.findByText("Juomat", { selector: "[data-name]" });
    expect(screen.queryByText("Muut", { selector: "[data-name]" })).not.toBeInTheDocument();
  });
});
