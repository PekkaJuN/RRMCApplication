import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it } from "vitest";
import { defaultItems, fakeCatalog, itemNamed, product } from "../test/catalog";
import { server } from "../test/server";
import { ProductsPage } from "./ProductsPage";

const items = defaultItems();

afterEach(() => {
  server.events.removeAllListeners();
});

function withProducts(...entries: [string, string][]) {
  const state = fakeCatalog(server);
  state.products = entries.map(([name, category], index) =>
    product(index + 1, name, itemNamed(state.items, category), state.items),
  );
  return state;
}

async function row(name: string): Promise<HTMLElement> {
  const table = await screen.findByRole("table", { name: "Tuotelista" });
  const cell = await within(table).findByText(name);
  const found = cell.closest("tr");
  if (!found) {
    throw new Error(`No row for ${name}`);
  }
  return found;
}

function rowNames(): string[] {
  const table = screen.getByRole("table", { name: "Tuotelista" });
  return within(table)
    .getAllByRole("row")
    .slice(1)
    .map((tableRow) => tableRow.querySelector("[data-name]")?.textContent ?? "");
}

function column(): HTMLElement {
  return screen.getByRole("region", { name: "Kategoriat" });
}

/** The selectable buttons of the category tree, in order. */
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

async function select(name: string): Promise<void> {
  await within(column()).findByRole("button", { name });
  await userEvent.click(treeItem(name));
}

// Changed to read the count beside the tree item instead of the panel's list item (G7 record).
function productCount(category: string): string | undefined {
  return treeItem(category).closest("li")?.querySelector("[data-count]")?.textContent ?? undefined;
}

/** The buttons with this name outside the product rows: the tools of the selected item. */
function toolButtons(name: string): HTMLElement[] {
  return screen.queryAllByRole("button", { name }).filter((button) => !button.closest("table"));
}

/** The product column, named by its heading: the selected item or "Kaikki tuotteet". */
function productColumn(name: string): HTMLElement {
  return screen.getByRole("region", { name });
}

function example() {
  return withProducts(
    ["Kevytmaito 1L", "Maitotuotteet"],
    ["Ruisleipä", "Leivät"],
    ["Moottoriöljy", "Autotarvikkeet"],
  );
}

/** Records the requests that reach the API, without answering them. */
function recordRequests() {
  const requests: string[] = [];
  server.events.on("request:start", ({ request }) => {
    const url = new URL(request.url);
    requests.push(`${request.method} ${url.pathname}${decodeURIComponent(url.search)}`);
  });
  return requests;
}

describe("ProductsPage", () => {
  it("AC30: the page is in Finnish", async () => {
    withProducts(["Kevytmaito 1L", "Maitotuotteet"]);
    render(<ProductsPage />);
    await row("Kevytmaito 1L");

    expect(screen.getByRole("heading", { name: "Tuotteet" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Kategoriat" })).toBeInTheDocument();
    expect(screen.getByRole("searchbox", { name: "Hae" })).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Lisää" }).length).toBeGreaterThan(0);
    expect(
      within(await row("Kevytmaito 1L")).getByRole("button", { name: "Poista" }),
    ).toBeInTheDocument();
    await userEvent.click(
      within(await row("Kevytmaito 1L")).getByRole("button", { name: "Nimeä" }),
    );
    expect(screen.getByRole("button", { name: "Tallenna" })).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Peruuta" }).length).toBeGreaterThan(0);
  });

  it("AC16: adds a product", async () => {
    withProducts();
    render(<ProductsPage />);

    const form = await screen.findByRole("form", { name: "Uusi tuote" });
    await userEvent.type(
      within(form).getByRole("textbox", { name: "Tuotteen nimi" }),
      "Kevytmaito 1L",
    );
    await userEvent.selectOptions(
      within(form).getByRole("combobox", { name: "Kategoria" }),
      "Maitotuotteet",
    );
    await userEvent.click(within(form).getByRole("button", { name: "Lisää" }));

    expect(await row("Kevytmaito 1L")).toHaveTextContent("Maitotuotteet");
    expect(productCount("Maitotuotteet")).toBe("1 tuote");
  });

  it("AC17, AC27: a duplicate is shown next to the add form and the list stays", async () => {
    withProducts(["Kevytmaito 1L", "Maitotuotteet"]);
    server.use(
      http.post("/api/products", () =>
        HttpResponse.json(
          { error: "duplicate_name", message: "Samanniminen tuote on jo olemassa." },
          { status: 409 },
        ),
      ),
    );
    render(<ProductsPage />);
    await row("Kevytmaito 1L");

    const form = screen.getByRole("form", { name: "Uusi tuote" });
    await userEvent.type(
      within(form).getByRole("textbox", { name: "Tuotteen nimi" }),
      "KEVYTMAITO 1l",
    );
    await userEvent.selectOptions(
      within(form).getByRole("combobox", { name: "Kategoria" }),
      "Juomat",
    );
    await userEvent.click(within(form).getByRole("button", { name: "Lisää" }));

    expect(await within(form).findByRole("alert")).toHaveTextContent(
      "Samanniminen tuote on jo olemassa.",
    );
    expect(rowNames()).toEqual(["Kevytmaito 1L"]);
  });

  it("AC20: choosing another category in the row recategorizes the product", async () => {
    withProducts(["Kevytmaito 1L", "Maitotuotteet"]);
    render(<ProductsPage />);

    await userEvent.selectOptions(
      within(await row("Kevytmaito 1L")).getByRole("combobox", { name: "Kategoria" }),
      "Juomat",
    );

    await expect.poll(() => productCount("Juomat")).toBe("1 tuote");
    expect(productCount("Maitotuotteet")).toBe("0 tuotetta");
    expect(
      within(await row("Kevytmaito 1L")).getByRole("combobox", { name: "Kategoria" }),
    ).toHaveDisplayValue("Juomat");
  });

  it("AC21: renames a product", async () => {
    withProducts(["Kevytmaito 1L", "Maitotuotteet"]);
    render(<ProductsPage />);

    const productRow = await row("Kevytmaito 1L");
    await userEvent.click(within(productRow).getByRole("button", { name: "Nimeä" }));
    const input = within(productRow).getByRole("textbox", { name: "Tuotteen nimi" });
    await userEvent.clear(input);
    await userEvent.type(input, "Kevytmaito 1,5L");
    await userEvent.click(within(productRow).getByRole("button", { name: "Tallenna" }));

    expect(await row("Kevytmaito 1,5L")).toBeInTheDocument();
  });

  it("AC22: deletes a product after confirmation", async () => {
    withProducts(["Kevytmaito 1L", "Maitotuotteet"], ["Ruisleipä", "Leivät"]);
    render(<ProductsPage />);

    const productRow = await row("Ruisleipä");
    await userEvent.click(within(productRow).getByRole("button", { name: "Poista" }));
    await userEvent.click(within(productRow).getByRole("button", { name: "Poista" }));

    await expect.poll(rowNames).toEqual(["Kevytmaito 1L"]);
    expect(productCount("Leivät")).toBe("0 tuotetta");
  });

  it("AC28: cancelling a delete sends no request", async () => {
    withProducts(["Kevytmaito 1L", "Maitotuotteet"]);
    render(<ProductsPage />);
    const productRow = await row("Kevytmaito 1L");
    const requests = recordRequests();

    await userEvent.click(within(productRow).getByRole("button", { name: "Poista" }));
    await userEvent.click(within(productRow).getByRole("button", { name: "Peruuta" }));

    expect(requests).toEqual([]);
    expect(rowNames()).toEqual(["Kevytmaito 1L"]);
  });

  it("AC23: searching asks the backend with q and shows the matches", async () => {
    withProducts(
      ["Kevytmaito 1L", "Maitotuotteet"],
      ["Rasvaton maito 1L", "Maitotuotteet"],
      ["Ruisleipä", "Leivät"],
    );
    render(<ProductsPage />);
    await row("Ruisleipä");
    const requests = recordRequests();

    await userEvent.type(screen.getByRole("searchbox", { name: "Hae" }), "MAITO");

    await screen.findByText("Rasvaton maito 1L");
    await expect.poll(rowNames).toEqual(["Kevytmaito 1L", "Rasvaton maito 1L"]);
    expect(requests).toContain("GET /api/products?q=MAITO");
  });

  it("AC24: a group filter with a search that matches nothing shows the empty state", async () => {
    withProducts(["Kevytmaito 1L", "Maitotuotteet"], ["Moottoriöljy", "Autotarvikkeet"]);
    render(<ProductsPage />);
    await row("Moottoriöljy");

    // Changed from the filter dropdown to the tree (G7 record).
    await select("Ruoka");
    await expect.poll(rowNames).toEqual(["Kevytmaito 1L"]);
    await userEvent.type(screen.getByRole("searchbox", { name: "Hae" }), "öljy");

    expect(await screen.findByText("Ehdoilla ei löytynyt tuotteita.")).toBeInTheDocument();
  });

  it("AC27: tells when the backend cannot be reached", async () => {
    server.use(
      http.get("/api/categories", () => HttpResponse.error()),
      http.get("/api/products", () => HttpResponse.error()),
    );
    render(<ProductsPage />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Taustapalveluun ei saada yhteyttä.",
    );
  });

  it("AC34: no products shows the empty state and the add form", async () => {
    withProducts();
    render(<ProductsPage />);

    expect(await screen.findByText("Ei tuotteita.")).toBeInTheDocument();
    expect(screen.getByRole("form", { name: "Uusi tuote" })).toBeInTheDocument();
  });

  it("AC34: with no categories the add form asks for a category first and sends nothing", async () => {
    fakeCatalog(server, []);
    render(<ProductsPage />);
    const form = await screen.findByRole("form", { name: "Uusi tuote" });
    await screen.findByText("Ei tuotteita.");
    const requests = recordRequests();

    await userEvent.type(within(form).getByRole("textbox", { name: "Tuotteen nimi" }), "Mehu");
    await userEvent.click(within(form).getByRole("button", { name: "Lisää" }));

    expect(within(form).getByText("Lisää ensin kategoria.")).toBeInTheDocument();
    expect(requests).toEqual([]);
  });

  it("AC27, AC34: a failed category load stays visible and does not claim there are no categories", async () => {
    withProducts(["Kevytmaito 1L", "Maitotuotteet"]);
    server.use(http.get("/api/categories", () => HttpResponse.error()));
    render(<ProductsPage />);

    await row("Kevytmaito 1L");
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Taustapalveluun ei saada yhteyttä.",
    );
    expect(screen.queryByText("Lisää ensin kategoria.")).not.toBeInTheDocument();
  });

  it("AC34: the no-category hint is not shown while the categories are loading", () => {
    withProducts();
    render(<ProductsPage />);

    expect(screen.queryByText("Lisää ensin kategoria.")).not.toBeInTheDocument();
  });

  it("AC24: a filter on a group that is deleted goes back to all products", async () => {
    const state = withProducts(["Kevytmaito 1L", "Maitotuotteet"]);
    state.items.push({
      id: 900,
      name: "Koti",
      kind: "group",
      parent_id: null,
      product_count: null,
      category_count: 0,
    });
    render(<ProductsPage />);
    await row("Kevytmaito 1L");

    // Changed from the filter dropdown and the panel's row to the tree and the tools (G7 record).
    await select("Koti");
    await screen.findByText("Ehdoilla ei löytynyt tuotteita.");
    await userEvent.click(toolButtons("Poista")[0] as HTMLElement);
    await userEvent.click(toolButtons("Poista")[0] as HTMLElement);

    expect(await row("Kevytmaito 1L")).toBeInTheDocument();
    expect(treeItem("Kaikki tuotteet")).toHaveAttribute("aria-pressed", "true");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("AC29: the add form lists categories under group headings", async () => {
    withProducts();
    render(<ProductsPage />);

    const form = await screen.findByRole("form", { name: "Uusi tuote" });
    await within(form).findByRole("option", { name: "Juomat" });
    const select = within(form).getByRole("combobox", { name: "Kategoria" });
    expect([...select.querySelectorAll("optgroup")].map((group) => group.label)).toEqual([
      itemNamed(items, "Auto").name,
      itemNamed(items, "Ruoka").name,
    ]);
  });

  it("AC1: the page opens with Kaikki tuotteet selected and all products", async () => {
    example();
    render(<ProductsPage />);
    await row("Ruisleipä");

    expect(treeItems().map((item) => item.textContent)).toEqual([
      "Kaikki tuotteet",
      ...items.map((item) => item.name),
    ]);
    expect(treeItem("Kaikki tuotteet")).toHaveAttribute("aria-pressed", "true");
    expect(treeItems().filter((item) => item.getAttribute("aria-pressed") === "true")).toHaveLength(
      1,
    );
    expect(productCount("Maitotuotteet")).toBe("1 tuote");
    expect(
      within(productColumn("Kaikki tuotteet")).getByRole("heading", { name: "Kaikki tuotteet" }),
    ).toBeInTheDocument();
    expect(rowNames()).toEqual(["Kevytmaito 1L", "Moottoriöljy", "Ruisleipä"]);
    expect(screen.queryByRole("combobox", { name: "Näytä" })).not.toBeInTheDocument();
    for (const name of ["Nimeä", "Muuta ryhmäksi", "Muuta kategoriaksi", "Poista"]) {
      expect(toolButtons(name)).toHaveLength(0);
    }
  });

  it("AC2: selecting a category asks for its products and names it in the heading", async () => {
    example();
    render(<ProductsPage />);
    await row("Ruisleipä");
    const requests = recordRequests();

    await select("Leivät");

    await expect.poll(rowNames).toEqual(["Ruisleipä"]);
    expect(requests).toContain(`GET /api/products?category_id=${itemNamed(items, "Leivät").id}`);
    expect(within(productColumn("Leivät")).getByRole("heading", { name: "Leivät" })).toBeVisible();
    expect(treeItem("Leivät")).toHaveAttribute("aria-pressed", "true");
    expect(treeItem("Kaikki tuotteet")).toHaveAttribute("aria-pressed", "false");
  });

  it("AC3: selecting a group shows the products of all its categories", async () => {
    example();
    render(<ProductsPage />);
    await row("Ruisleipä");

    await select("Ruoka");

    await expect.poll(rowNames).toEqual(["Kevytmaito 1L", "Ruisleipä"]);
    expect(productColumn("Ruoka")).toBeInTheDocument();
  });

  it("AC4: the search combines with the selection and stays when the selection changes", async () => {
    example();
    render(<ProductsPage />);
    await row("Ruisleipä");
    await select("Ruoka");
    await expect.poll(rowNames).toEqual(["Kevytmaito 1L", "Ruisleipä"]);

    await userEvent.type(screen.getByRole("searchbox", { name: "Hae" }), "öljy");
    expect(await screen.findByText("Ehdoilla ei löytynyt tuotteita.")).toBeInTheDocument();
    await select("Kaikki tuotteet");

    expect(await row("Moottoriöljy")).toBeInTheDocument();
    expect(rowNames()).toEqual(["Moottoriöljy"]);
    expect(screen.getByRole("searchbox", { name: "Hae" })).toHaveValue("öljy");
  });

  it("AC6: closing a group keeps the selection and its products", async () => {
    example();
    render(<ProductsPage />);
    await row("Ruisleipä");
    await select("Leivät");
    await expect.poll(rowNames).toEqual(["Ruisleipä"]);

    await userEvent.click(
      within(column()).getByRole("button", { name: "Piilota kategoriat: Ruoka" }),
    );

    expect(rowNames()).toEqual(["Ruisleipä"]);
    expect(productColumn("Leivät")).toBeInTheDocument();
  });

  it("AC8, AC9: the tools of the selected item stand in the product column", async () => {
    example();
    render(<ProductsPage />);
    await row("Ruisleipä");

    await select("Maitotuotteet");
    const maito = productColumn("Maitotuotteet");
    expect(
      within(maito).getByRole("combobox", { name: "Ryhmä: Maitotuotteet" }),
    ).toHaveDisplayValue("Ruoka");
    for (const name of ["Nimeä", "Muuta ryhmäksi", "Poista"]) {
      expect(toolButtons(name)).toHaveLength(1);
      expect(maito).toContainElement(toolButtons(name)[0] as HTMLElement);
    }

    await select("Ruoka");
    for (const name of ["Nimeä", "Muuta kategoriaksi", "Poista"]) {
      expect(toolButtons(name)).toHaveLength(1);
    }
    expect(screen.queryByRole("combobox", { name: "Ryhmä: Ruoka" })).not.toBeInTheDocument();
  });

  it("AC10: renaming the selected item keeps it selected", async () => {
    example();
    render(<ProductsPage />);
    await row("Ruisleipä");
    await select("Leivät");

    await userEvent.click(toolButtons("Nimeä")[0] as HTMLElement);
    const input = screen.getByRole("textbox", { name: "Kategorian nimi" });
    await userEvent.clear(input);
    await userEvent.type(input, "Leipä");
    await userEvent.click(screen.getByRole("button", { name: "Tallenna" }));

    expect(await within(column()).findByRole("button", { name: "Leipä" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(productColumn("Leipä")).toBeInTheDocument();
    expect(rowNames()).toEqual(["Ruisleipä"]);
  });

  it("AC11: moving the selected category out of its group keeps it selected", async () => {
    example();
    render(<ProductsPage />);
    await row("Ruisleipä");
    await select("Maitotuotteet");

    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Ryhmä: Maitotuotteet" }),
      "Ei ryhmää",
    );

    await expect.poll(() => productCount("Ruoka")).toBe("9 kategoriaa");
    const group = treeItem("Maitotuotteet").closest("li")?.parentElement?.closest("li");
    expect(group).toBeNull();
    expect(treeItem("Maitotuotteet")).toHaveAttribute("aria-pressed", "true");
    expect(rowNames()).toEqual(["Kevytmaito 1L"]);
  });

  it("AC12: converting the selected item keeps it selected and changes its tools", async () => {
    example();
    render(<ProductsPage />);
    await row("Ruisleipä");
    await select("Lemmikit");

    await userEvent.click(toolButtons("Muuta ryhmäksi")[0] as HTMLElement);

    await expect.poll(() => productCount("Lemmikit")).toBe("0 kategoriaa");
    expect(treeItem("Lemmikit")).toHaveAttribute("aria-pressed", "true");
    expect(toolButtons("Muuta kategoriaksi")).toHaveLength(1);

    await userEvent.click(toolButtons("Muuta kategoriaksi")[0] as HTMLElement);

    await expect.poll(() => productCount("Lemmikit")).toBe("0 tuotetta");
    expect(treeItem("Lemmikit")).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("combobox", { name: "Ryhmä: Lemmikit" })).toHaveDisplayValue(
      "Ei ryhmää",
    );
  });

  it("AC13: a refused action shows its message beside the tools and keeps the selection", async () => {
    example();
    server.use(
      http.patch("/api/categories/:id", () =>
        HttpResponse.json(
          {
            error: "category_has_products",
            message: "Kategoriaa, jossa on tuotteita tai kuittirivejä, ei voi muuttaa ryhmäksi.",
          },
          { status: 409 },
        ),
      ),
    );
    render(<ProductsPage />);
    await row("Ruisleipä");
    await select("Juomat");

    await userEvent.click(toolButtons("Muuta ryhmäksi")[0] as HTMLElement);

    expect(await within(productColumn("Juomat")).findByRole("alert")).toHaveTextContent(
      "Kategoriaa, jossa on tuotteita tai kuittirivejä, ei voi muuttaa ryhmäksi.",
    );
    expect(treeItem("Juomat")).toHaveAttribute("aria-pressed", "true");
  });

  it("AC14: deleting the selected item selects Kaikki tuotteet; cancelling sends nothing", async () => {
    example();
    render(<ProductsPage />);
    await row("Ruisleipä");
    await select("Lemmikit");
    const requests = recordRequests();

    await userEvent.click(toolButtons("Poista")[0] as HTMLElement);
    await userEvent.click(screen.getByRole("button", { name: "Peruuta" }));
    expect(requests).toEqual([]);

    await userEvent.click(toolButtons("Poista")[0] as HTMLElement);
    await userEvent.click(toolButtons("Poista")[0] as HTMLElement);

    expect(await screen.findByRole("region", { name: "Kaikki tuotteet" })).toBeInTheDocument();
    expect(treeItems().map((item) => item.textContent)).not.toContain("Lemmikit");
    expect(treeItem("Kaikki tuotteet")).toHaveAttribute("aria-pressed", "true");
    await expect.poll(rowNames).toEqual(["Kevytmaito 1L", "Moottoriöljy", "Ruisleipä"]);
  });

  it("AC18: a new product starts in the selected category", async () => {
    example();
    render(<ProductsPage />);
    await row("Ruisleipä");
    const form = screen.getByRole("form", { name: "Uusi tuote" });
    const category = within(form).getByRole("combobox", { name: "Kategoria" });

    await select("Leivät");
    expect(category).toHaveDisplayValue("Leivät");
    await userEvent.type(
      within(form).getByRole("textbox", { name: "Tuotteen nimi" }),
      "Näkkileipä",
    );
    await userEvent.click(within(form).getByRole("button", { name: "Lisää" }));

    await expect.poll(rowNames).toEqual(["Näkkileipä", "Ruisleipä"]);
    expect(productCount("Leivät")).toBe("2 tuotetta");

    await select("Ruoka");
    expect(category).toHaveDisplayValue("Valitse kategoria");
  });

  it("AC18: the user's own choice holds until the selection changes", async () => {
    example();
    render(<ProductsPage />);
    await row("Ruisleipä");
    const form = screen.getByRole("form", { name: "Uusi tuote" });
    const category = within(form).getByRole("combobox", { name: "Kategoria" });
    await select("Leivät");

    await userEvent.selectOptions(category, "Juomat");
    expect(category).toHaveDisplayValue("Juomat");
    await select("Maitotuotteet");

    expect(category).toHaveDisplayValue("Maitotuotteet");
  });

  it("AC19: recategorizing a product out of the selected category removes it from the list", async () => {
    example();
    render(<ProductsPage />);
    await row("Ruisleipä");
    await select("Leivät");
    await expect.poll(rowNames).toEqual(["Ruisleipä"]);

    await userEvent.selectOptions(
      within(await row("Ruisleipä")).getByRole("combobox", { name: "Kategoria" }),
      "Juomat",
    );

    expect(await screen.findByText("Ehdoilla ei löytynyt tuotteita.")).toBeInTheDocument();
    expect(productCount("Leivät")).toBe("0 tuotetta");
    expect(productCount("Juomat")).toBe("1 tuote");
  });

  it("AC20: with a failed category load the tree has only Kaikki tuotteet", async () => {
    example();
    server.use(http.get("/api/categories", () => HttpResponse.error()));
    render(<ProductsPage />);

    await row("Ruisleipä");
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Taustapalveluun ei saada yhteyttä.",
    );
    expect(treeItems().map((item) => item.textContent)).toEqual(["Kaikki tuotteet"]);
    expect(treeItem("Kaikki tuotteet")).toHaveAttribute("aria-pressed", "true");
    expect(rowNames()).toEqual(["Kevytmaito 1L", "Moottoriöljy", "Ruisleipä"]);
    expect(screen.queryByText("Lisää ensin kategoria.")).not.toBeInTheDocument();
  });
});
