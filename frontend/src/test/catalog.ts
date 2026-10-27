import { http, HttpResponse } from "msw";
import type { SetupServer } from "msw/node";
import type { CatalogItem, Product } from "../api/catalog";

const GROUPS: [string, string[]][] = [
  ["Auto", ["Autohuolto", "Autotarvikkeet", "Polttoaineet"]],
  [
    "Ruoka",
    [
      "Hedelmät",
      "Kala",
      "Kananmunat",
      "Kuivatuotteet",
      "Leivät",
      "Liha",
      "Lihan korvaajat",
      "Maitotuotteet",
      "Pakasteet",
      "Vihannekset",
    ],
  ],
];
const UNGROUPED = [
  "Alkoholi",
  "Herkut",
  "Hygienia",
  "Juomat",
  "Kodin tarvikkeet",
  "Lemmikit",
  "Muut",
  "Ulkona syöminen",
];

/** The default list in the backend's order: groups with their categories, then ungrouped. */
export function defaultItems(): CatalogItem[] {
  let id = 0;
  const items: CatalogItem[] = [];
  const category = (name: string, parentId: number | null): CatalogItem => ({
    id: ++id,
    name,
    kind: "category",
    parent_id: parentId,
    product_count: 0,
    category_count: null,
  });
  for (const [group, categories] of GROUPS) {
    const groupId = ++id;
    items.push({
      id: groupId,
      name: group,
      kind: "group",
      parent_id: null,
      product_count: null,
      category_count: categories.length,
    });
    items.push(...categories.map((name) => category(name, groupId)));
  }
  items.push(...UNGROUPED.map((name) => category(name, null)));
  return items;
}

export function itemNamed(items: CatalogItem[], name: string): CatalogItem {
  const item = items.find((candidate) => candidate.name === name);
  if (!item) {
    throw new Error(`No test item ${name}`);
  }
  return item;
}

export function product(
  id: number,
  name: string,
  category: CatalogItem,
  items: CatalogItem[],
): Product {
  const group = items.find((item) => item.id === category.parent_id);
  return {
    id,
    name,
    category_id: category.id,
    category_name: category.name,
    group_name: group ? group.name : null,
  };
}

/**
 * An in-memory catalog behind MSW handlers, for components that write and then reload.
 * It applies changes without the backend's rules. Tests add error answers with
 * `server.use` after calling it, because MSW prefers the handlers added last.
 */
export function fakeCatalog(server: SetupServer, initial: CatalogItem[] = defaultItems()) {
  const state = { items: initial.map((item) => ({ ...item })), products: [] as Product[] };
  let nextId = 1000;

  const counted = (): CatalogItem[] =>
    state.items.map((item) =>
      item.kind === "group"
        ? {
            ...item,
            product_count: null,
            category_count: state.items.filter((child) => child.parent_id === item.id).length,
          }
        : {
            ...item,
            category_count: null,
            product_count: state.products.filter((p) => p.category_id === item.id).length,
          },
    );
  const withNames = (raw: { id: number; name: string; category_id: number }): Product => {
    const category = state.items.find((item) => item.id === raw.category_id);
    if (!category) {
      throw new Error(`No test category ${raw.category_id}`);
    }
    return product(raw.id, raw.name, category, state.items);
  };

  server.use(
    http.get("/api/categories", () => HttpResponse.json(counted())),
    http.post("/api/categories", async ({ request }) => {
      const body = (await request.json()) as Pick<CatalogItem, "name" | "kind"> & {
        parent_id?: number | null;
      };
      const item: CatalogItem = {
        id: nextId++,
        name: body.name.trim(),
        kind: body.kind,
        parent_id: body.parent_id ?? null,
        product_count: null,
        category_count: null,
      };
      state.items.push(item);
      return HttpResponse.json(item, { status: 201 });
    }),
    http.patch("/api/categories/:id", async ({ request, params }) => {
      const changes = (await request.json()) as Partial<CatalogItem>;
      const id = Number(params.id);
      state.items = state.items.map((item) => (item.id === id ? { ...item, ...changes } : item));
      return HttpResponse.json(counted().find((item) => item.id === id));
    }),
    http.delete("/api/categories/:id", ({ params }) => {
      state.items = state.items.filter((item) => item.id !== Number(params.id));
      return new HttpResponse(null, { status: 204 });
    }),
    http.get("/api/products", ({ request }) => {
      const url = new URL(request.url);
      const q = (url.searchParams.get("q") ?? "").toLowerCase();
      const filter = url.searchParams.get("category_id");
      const inFilter = (p: Product) => {
        if (filter === null) {
          return true;
        }
        const category = state.items.find((item) => item.id === p.category_id);
        return p.category_id === Number(filter) || category?.parent_id === Number(filter);
      };
      const rows = state.products
        .map(withNames)
        .filter((p) => p.name.toLowerCase().includes(q) && inFilter(p))
        .sort((a, b) => a.name.localeCompare(b.name, "fi"));
      return HttpResponse.json(rows);
    }),
    http.post("/api/products", async ({ request }) => {
      const body = (await request.json()) as { name: string; category_id: number };
      const created = withNames({
        id: nextId++,
        name: body.name.trim(),
        category_id: body.category_id,
      });
      state.products.push(created);
      return HttpResponse.json(created, { status: 201 });
    }),
    http.patch("/api/products/:id", async ({ request, params }) => {
      const changes = (await request.json()) as Partial<Product>;
      const id = Number(params.id);
      state.products = state.products.map((p) =>
        p.id === id ? withNames({ ...p, ...changes }) : p,
      );
      return HttpResponse.json(state.products.find((p) => p.id === id));
    }),
    http.delete("/api/products/:id", ({ params }) => {
      state.products = state.products.filter((p) => p.id !== Number(params.id));
      return new HttpResponse(null, { status: 204 });
    }),
  );
  return state;
}
