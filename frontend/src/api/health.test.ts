import { http, HttpResponse } from "msw";
import { expect, it } from "vitest";
import { server } from "../test/server";
import { getHealth, type Health } from "./health";

it("AC23: reads GET /api/health", async () => {
  const health: Health = {
    status: "ok",
    model_name: "qwen2.5:7b",
    checks: { database: "ok", folders: "ok", ocr: "ok", model: "ok" },
  };
  server.use(http.get("/api/health", () => HttpResponse.json(health)));

  expect(await getHealth()).toEqual({ ok: true, data: health });
});
