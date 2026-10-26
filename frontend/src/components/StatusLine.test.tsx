import { act, render, screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Health } from "../api/health";
import { server } from "../test/server";
import { StatusLine } from "./StatusLine";

function makeHealth(checks: Partial<Health["checks"]> = {}, modelName = "qwen2.5:7b"): Health {
  const allChecks: Health["checks"] = {
    database: "ok",
    folders: "ok",
    ocr: "ok",
    model: "ok",
    ...checks,
  };
  const isOk = Object.values(allChecks).every((value) => value === "ok");
  return { status: isOk ? "ok" : "degraded", model_name: modelName, checks: allChecks };
}

function answerHealth(...answers: Health[]): void {
  let calls = 0;
  server.use(
    http.get("/api/health", () => {
      const answer = answers[Math.min(calls, answers.length - 1)];
      calls += 1;
      return HttpResponse.json(answer);
    }),
  );
}

async function shownTexts(): Promise<string[]> {
  const status = screen.getByRole("status", { name: "Palveluiden tila" });
  const items = await within(status).findAllByRole("listitem");
  return items.map((item) => item.textContent ?? "");
}

describe("StatusLine", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it.each([
    [makeHealth(), "Kaikki palvelut toiminnassa"],
    [makeHealth({ model: "unavailable" }), "Ollamaan ei saada yhteyttä. Käynnistä Ollama."],
    [
      makeHealth({ model: "missing_model" }, "llama3"),
      "Mallia llama3 ei ole ladattu. Lataa se komennolla: ollama pull llama3",
    ],
    [makeHealth({ ocr: "unavailable" }), "Tekstintunnistus ei ole käytettävissä."],
    [
      makeHealth({ folders: "unavailable" }),
      "Kuvakansioita ei löydy tai niihin ei voi kirjoittaa.",
    ],
    [makeHealth({ database: "unavailable" }), "Tietokanta ei ole käytettävissä."],
  ])("AC23: shows the text of each health result (%#)", async (health, text) => {
    answerHealth(health);

    render(<StatusLine />);

    expect(await shownTexts()).toEqual([text]);
  });

  it("AC23: shows every failing check", async () => {
    answerHealth(makeHealth({ model: "unavailable", folders: "unavailable" }));

    render(<StatusLine />);

    expect(await shownTexts()).toEqual([
      "Ollamaan ei saada yhteyttä. Käynnistä Ollama.",
      "Kuvakansioita ei löydy tai niihin ei voi kirjoittaa.",
    ]);
  });

  it("AC23: tells when the backend does not answer", async () => {
    server.use(http.get("/api/health", () => HttpResponse.error()));

    render(<StatusLine />);

    expect(await shownTexts()).toEqual(["Taustapalveluun ei saada yhteyttä."]);
  });

  it("AC24: refreshes every 30 seconds without reloading", async () => {
    // Only the refresh interval is faked; fetch and MSW keep their own timers.
    vi.useFakeTimers({ toFake: ["setInterval", "clearInterval"] });
    answerHealth(makeHealth({ model: "unavailable" }), makeHealth());
    render(<StatusLine />);
    expect(await shownTexts()).toEqual(["Ollamaan ei saada yhteyttä. Käynnistä Ollama."]);

    act(() => {
      vi.advanceTimersByTime(30_000);
    });

    expect(await screen.findByText("Kaikki palvelut toiminnassa")).toBeInTheDocument();
  });

  it("AC24: stops refreshing when removed from the page", async () => {
    vi.useFakeTimers({ toFake: ["setInterval", "clearInterval"] });
    answerHealth(makeHealth());
    // fetch is called synchronously when a refresh starts, unlike the MSW handler.
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    const { unmount } = render(<StatusLine />);
    await shownTexts();

    unmount();
    vi.advanceTimersByTime(60_000);

    expect(fetchSpy).toHaveBeenCalledTimes(1);
  });
});
