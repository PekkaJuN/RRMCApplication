import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { server } from "../test/server";
import {
  createCategory,
  createProduct,
  deleteCategory,
  deleteProduct,
  listCategories,
  listProducts,
  updateCategory,
  updateProduct,
} from "./catalog";

/** Records the method, path, query and body of the request and answers with `answer`. */
function record(answer: () => Response) {
  const calls: { method: string; path: string; query: string; body: unknown }[] = [];
  server.use(
    http.all("/api/*", async ({ request }) => {
      const url = new URL(request.url);
      const text = await request.text();
      calls.push({
        method: request.method,
        path: url.pathname,
        query: url.search,
        body: text ? (JSON.parse(text) as unknown) : undefined,
      });
      return answer();
    }),
  );
  return calls;
}

const ok = () => HttpResponse.json([]);

describe("catalog client", () => {
  it("AC27: categories use their paths and methods", async () => {
    const calls = record(ok);

    await listCategories();
    await createCategory({ name: "Koti", kind: "group" });
    await updateCategory(5, { parent_id: null });
    await deleteCategory(5);

    expect(calls).toEqual([
      { method: "GET", path: "/api/categories", query: "", body: undefined },
      {
        method: "POST",
        path: "/api/categories",
        query: "",
        body: { name: "Koti", kind: "group" },
      },
      { method: "PATCH", path: "/api/categories/5", query: "", body: { parent_id: null } },
      { method: "DELETE", path: "/api/categories/5", query: "", body: undefined },
    ]);
  });

  it("AC27: products use their paths and methods", async () => {
    const calls = record(ok);

    await createProduct({ name: "Mehu", category_id: 2 });
    await updateProduct(7, { category_id: 3 });
    await deleteProduct(7);

    expect(calls.map(({ method, path, body }) => ({ method, path, body }))).toEqual([
      { method: "POST", path: "/api/products", body: { name: "Mehu", category_id: 2 } },
      { method: "PATCH", path: "/api/products/7", body: { category_id: 3 } },
      { method: "DELETE", path: "/api/products/7", body: undefined },
    ]);
  });

  it("AC23, AC24: listProducts sends only the filters that are given", async () => {
    const calls = record(ok);

    await listProducts({});
    await listProducts({ q: "maito" });
    await listProducts({ q: "", categoryId: 4 });
    await listProducts({ q: "öljy", categoryId: 4 });

    expect(calls.map(({ query }) => decodeURIComponent(query))).toEqual([
      "",
      "?q=maito",
      "?category_id=4",
      "?q=öljy&category_id=4",
    ]);
  });
});
