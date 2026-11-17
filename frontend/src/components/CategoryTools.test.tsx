import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { useCallback, useEffect, useState } from "react";
import { beforeEach, describe, expect, it } from "vitest";
import { listCategories, type CatalogItem } from "../api/catalog";
import { defaultItems, fakeCatalog } from "../test/catalog";
import { server } from "../test/server";
import { CategoryTools } from "./CategoryTools";

type CatalogState = ReturnType<typeof fakeCatalog>;

/** Loads the categories, shows the tools of one item and reloads after a change, as the page does. */
function Harness({ id }: { id: number }) {
  const [items, setItems] = useState<CatalogItem[]>([]);
  const reload = useCallback(() => {
    void listCategories().then((result) => {
      if (result.ok) {
        setItems(result.data);
      }
    });
  }, []);
  useEffect(reload, [reload]);
  const item = items.find((candidate) => candidate.id === id);
  const groups = items.filter((candidate) => candidate.kind === "group");
  return item ? (
    <CategoryTools item={item} groups={groups} onChanged={reload} />
  ) : (
    <p>{items.length > 0 ? "poistettu" : "ladataan"}</p>
  );
}

function idOf(name: string, items: CatalogItem[] = defaultItems()): number {
  const item = items.find((candidate) => candidate.name === name);
  if (!item) {
    throw new Error(`No test item ${name}`);
  }
  return item.id;
}

function stateItem(state: CatalogState, name: string): CatalogItem | undefined {
  return state.items.find((item) => item.name === name);
}

let state: CatalogState;

beforeEach(() => {
  state = fakeCatalog(server);
});

describe("CategoryTools", () => {
  it("AC8: a category has rename, its group, convert to a group and delete", async () => {
    render(<Harness id={idOf("Maitotuotteet")} />);

    expect(await screen.findByRole("button", { name: "Nimeä" })).toBeInTheDocument();
    const group = screen.getByRole("combobox", { name: "Ryhmä: Maitotuotteet" });
    expect(group).toHaveDisplayValue("Ruoka");
    expect(screen.getByRole("button", { name: "Muuta ryhmäksi" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Poista" })).toBeInTheDocument();
  });

  it("AC9: a group has rename, convert to a category and delete, but no group dropdown", async () => {
    render(<Harness id={idOf("Ruoka")} />);

    expect(await screen.findByRole("button", { name: "Nimeä" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Muuta kategoriaksi" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Poista" })).toBeInTheDocument();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
  });

  // Moved from CategoryPanel.test.tsx (product management AC6, G7 record).
  it("product management AC6: renames a category", async () => {
    render(<Harness id={idOf("Juomat")} />);

    await userEvent.click(await screen.findByRole("button", { name: "Nimeä" }));
    const input = screen.getByRole("textbox", { name: "Kategorian nimi" });
    await userEvent.clear(input);
    await userEvent.type(input, "Virvoitusjuomat");
    await userEvent.click(screen.getByRole("button", { name: "Tallenna" }));

    expect(await screen.findByRole("combobox", { name: "Ryhmä: Virvoitusjuomat" })).toBeVisible();
    expect(stateItem(state, "Virvoitusjuomat")).toBeDefined();
  });

  it("AC10: Peruuta closes the rename form and keeps the name", async () => {
    render(<Harness id={idOf("Juomat")} />);

    await userEvent.click(await screen.findByRole("button", { name: "Nimeä" }));
    await userEvent.type(screen.getByRole("textbox", { name: "Kategorian nimi" }), "x");
    await userEvent.click(screen.getByRole("button", { name: "Peruuta" }));

    expect(screen.queryByRole("textbox", { name: "Kategorian nimi" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Nimeä" })).toBeInTheDocument();
    expect(stateItem(state, "Juomat")).toBeDefined();
  });

  it("AC11: moves a category into another group", async () => {
    render(<Harness id={idOf("Juomat")} />);

    await userEvent.selectOptions(
      await screen.findByRole("combobox", { name: "Ryhmä: Juomat" }),
      "Ruoka",
    );

    await waitFor(() => expect(stateItem(state, "Juomat")?.parent_id).toBe(idOf("Ruoka")));
  });

  // Moved from CategoryPanel.test.tsx (product management AC9, G7 record).
  it("product management AC9: moves a category out of its group", async () => {
    render(<Harness id={idOf("Pakasteet")} />);

    await userEvent.selectOptions(
      await screen.findByRole("combobox", { name: "Ryhmä: Pakasteet" }),
      "Ei ryhmää",
    );

    await waitFor(() => expect(stateItem(state, "Pakasteet")?.parent_id).toBeNull());
    expect(await screen.findByRole("combobox", { name: "Ryhmä: Pakasteet" })).toHaveDisplayValue(
      "Ei ryhmää",
    );
  });

  // Moved from CategoryPanel.test.tsx (product management AC11, G7 record).
  it("product management AC11: converts an empty group into a category", async () => {
    const koti: CatalogItem = {
      id: 500,
      name: "Koti",
      kind: "group",
      parent_id: null,
      product_count: null,
      category_count: 0,
    };
    state = fakeCatalog(server, [...defaultItems(), koti]);
    render(<Harness id={500} />);

    await userEvent.click(await screen.findByRole("button", { name: "Muuta kategoriaksi" }));

    expect(await screen.findByRole("button", { name: "Muuta ryhmäksi" })).toBeInTheDocument();
    expect(stateItem(state, "Koti")?.kind).toBe("category");
  });

  // Moved from CategoryPanel.test.tsx (product management AC12, AC27, G7 record).
  it("product management AC12, AC27: a refused conversion shows the message beside the tools", async () => {
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
    render(<Harness id={idOf("Juomat")} />);

    await userEvent.click(await screen.findByRole("button", { name: "Muuta ryhmäksi" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Kategoriaa, jossa on tuotteita, ei voi muuttaa ryhmäksi.",
    );
    expect(stateItem(state, "Juomat")?.kind).toBe("category");
  });

  // Moved from CategoryPanel.test.tsx (product management AC13, AC27, G7 record).
  it("product management AC13, AC27: a category in use is not deleted and tells the count", async () => {
    server.use(
      http.delete("/api/categories/:id", () =>
        HttpResponse.json(
          { error: "category_in_use", message: "Kategoriaa käyttää 3 tuotetta.", product_count: 3 },
          { status: 409 },
        ),
      ),
    );
    render(<Harness id={idOf("Juomat")} />);

    await userEvent.click(await screen.findByRole("button", { name: "Poista" }));
    await userEvent.click(screen.getByRole("button", { name: "Poista" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Kategoriaa käyttää 3 tuotetta.");
    expect(stateItem(state, "Juomat")).toBeDefined();
  });

  // Moved from CategoryPanel.test.tsx (product management AC14, G7 record).
  it("product management AC14: a group with categories is not deleted", async () => {
    server.use(
      http.delete("/api/categories/:id", () =>
        HttpResponse.json(
          { error: "group_not_empty", message: "Ryhmässä on 3 kategoriaa.", category_count: 3 },
          { status: 409 },
        ),
      ),
    );
    render(<Harness id={idOf("Auto")} />);

    await userEvent.click(await screen.findByRole("button", { name: "Poista" }));
    await userEvent.click(screen.getByRole("button", { name: "Poista" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Ryhmässä on 3 kategoriaa.");
    expect(stateItem(state, "Auto")).toBeDefined();
  });

  // Moved from CategoryPanel.test.tsx (product management AC28, G7 record).
  it("product management AC28: cancelling a category delete sends no request", async () => {
    render(<Harness id={idOf("Juomat")} />);
    const askDelete = await screen.findByRole("button", { name: "Poista" });
    const requests: string[] = [];
    const record = ({ request }: { request: Request }) => {
      requests.push(request.method);
    };
    server.events.on("request:start", record);

    await userEvent.click(askDelete);
    await userEvent.click(screen.getByRole("button", { name: "Peruuta" }));

    server.events.removeListener("request:start", record);
    expect(requests).toEqual([]);
    expect(stateItem(state, "Juomat")).toBeDefined();
  });

  // Moved from CategoryPanel.test.tsx (product management AC15, G7 record).
  it("product management AC15: deletes an unused category after confirmation", async () => {
    render(<Harness id={idOf("Muut")} />);

    await userEvent.click(await screen.findByRole("button", { name: "Poista" }));
    await userEvent.click(screen.getByRole("button", { name: "Poista" }));

    expect(await screen.findByText("poistettu")).toBeInTheDocument();
    expect(stateItem(state, "Muut")).toBeUndefined();
  });
});
