import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { server } from "../test/server";
import { apiGet } from "./client";

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
