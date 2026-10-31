import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { server } from "../test/server";
import { apiDelete, apiGet, apiPatch, apiPost } from "./client";

describe("apiGet", () => {
  it("AC23: returns the data of a successful response", async () => {
    server.use(http.get("/api/things", () => HttpResponse.json({ name: "a" })));

    const result = await apiGet<{ name: string }>("/api/things");

    expect(result).toEqual({ ok: true, data: { name: "a" } });
  });

  it("AC23: returns the code and Finnish message of an error response", async () => {
    server.use(
      http.get("/api/things", () =>
        HttpResponse.json(
          { error: "not_found", message: "Pyydettyä kohdetta ei löydy." },
          { status: 404 },
        ),
      ),
    );

    const result = await apiGet("/api/things");

    expect(result).toEqual({
      ok: false,
      error: { code: "not_found", message: "Pyydettyä kohdetta ei löydy." },
    });
  });

  it("AC23: a network error tells that the backend cannot be reached", async () => {
    server.use(http.get("/api/things", () => HttpResponse.error()));

    const result = await apiGet("/api/things");

    expect(result).toEqual({
      ok: false,
      error: { code: "network_error", message: "Taustapalveluun ei saada yhteyttä." },
    });
  });

  it("AC23: an error without the API error format tells that the backend cannot be reached", async () => {
    // The Vite proxy answers this way when the backend container does not answer.
    server.use(http.get("/api/things", () => new HttpResponse("proxy error", { status: 502 })));

    const result = await apiGet("/api/things");

    expect(result).toEqual({
      ok: false,
      error: { code: "network_error", message: "Taustapalveluun ei saada yhteyttä." },
    });
  });
});

describe("write methods", () => {
  it("AC27: apiPost sends the JSON body and returns the created item", async () => {
    let received: unknown;
    server.use(
      http.post("/api/things", async ({ request }) => {
        received = await request.json();
        return HttpResponse.json({ id: 1, name: "a" }, { status: 201 });
      }),
    );

    const result = await apiPost<{ id: number; name: string }>("/api/things", { name: "a" });

    expect(received).toEqual({ name: "a" });
    expect(result).toEqual({ ok: true, data: { id: 1, name: "a" } });
  });

  it("AC27: apiPatch sends the JSON body with PATCH", async () => {
    let received: unknown;
    server.use(
      http.patch("/api/things/1", async ({ request }) => {
        received = await request.json();
        return HttpResponse.json({ id: 1, name: "b" });
      }),
    );

    const result = await apiPatch<{ id: number; name: string }>("/api/things/1", { name: "b" });

    expect(received).toEqual({ name: "b" });
    expect(result).toEqual({ ok: true, data: { id: 1, name: "b" } });
  });

  it("AC27: apiDelete succeeds on 204 without a body", async () => {
    server.use(http.delete("/api/things/1", () => new HttpResponse(null, { status: 204 })));

    const result = await apiDelete("/api/things/1");

    expect(result).toEqual({ ok: true, data: undefined });
  });

  it("line-editing AC31: apiDelete returns the body when the answer has one", async () => {
    server.use(http.delete("/api/things/1", () => HttpResponse.json({ id: 1, name: "a" })));

    const result = await apiDelete<{ id: number; name: string }>("/api/things/1");

    expect(result).toEqual({ ok: true, data: { id: 1, name: "a" } });
  });

  it("AC27: a write that is refused returns the code and Finnish message", async () => {
    server.use(
      http.delete("/api/things/1", () =>
        HttpResponse.json(
          { error: "category_in_use", message: "Kategoriaa käyttää 3 tuotetta.", product_count: 3 },
          { status: 409 },
        ),
      ),
    );

    const result = await apiDelete("/api/things/1");

    expect(result).toEqual({
      ok: false,
      error: { code: "category_in_use", message: "Kategoriaa käyttää 3 tuotetta." },
    });
  });

  it("AC27: a write that cannot reach the backend tells so", async () => {
    server.use(http.post("/api/things", () => HttpResponse.error()));

    const result = await apiPost("/api/things", {});

    expect(result).toEqual({
      ok: false,
      error: { code: "network_error", message: "Taustapalveluun ei saada yhteyttä." },
    });
  });
});
