import { http, HttpResponse } from "msw";
import { expect, it } from "vitest";
import { FINISHED, running } from "../test/imports";
import { server } from "../test/server";
import { getImport, startImport } from "./imports";

it("AC27: reads the state with GET /api/import", async () => {
  server.use(http.get("/api/import", () => HttpResponse.json(FINISHED)));

  expect(await getImport()).toEqual({ ok: true, data: FINISHED });
});

it("AC27: starts a run with POST /api/import", async () => {
  server.use(http.post("/api/import", () => HttpResponse.json(running(0, 4), { status: 202 })));

  expect(await startImport()).toEqual({ ok: true, data: running(0, 4) });
});

it("AC29: a refused start keeps the code and message", async () => {
  server.use(
    http.post("/api/import", () =>
      HttpResponse.json(
        { error: "import_running", message: "Tuonti on jo käynnissä." },
        { status: 409 },
      ),
    ),
  );

  expect(await startImport()).toEqual({
    ok: false,
    error: { code: "import_running", message: "Tuonti on jo käynnissä." },
  });
});
