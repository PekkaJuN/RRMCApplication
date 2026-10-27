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

function productCount(category: string): string | undefined {
  const label = screen.getByText(category, { selector: "[data-name]" });
  return label.nextElementSibling?.textContent ?? undefined;
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

    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Näytä" }),
      "Ruoka (koko ryhmä)",
    );
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

    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Näytä" }),
      "Koti (koko ryhmä)",
    );
    await screen.findByText("Ehdoilla ei löytynyt tuotteita.");
    const koti = screen.getByText("Koti", { selector: "[data-name]" }).closest("li") as HTMLElement;
    await userEvent.click(within(koti).getByRole("button", { name: "Poista" }));
    await userEvent.click(within(koti).getByRole("button", { name: "Poista" }));

    expect(await row("Kevytmaito 1L")).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Näytä" })).toHaveDisplayValue("Kaikki");
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
});
