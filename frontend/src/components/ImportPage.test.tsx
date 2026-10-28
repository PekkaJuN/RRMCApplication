import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import type { ImportState } from "../api/imports";
import { FINISHED, IDLE, running } from "../test/imports";
import { server } from "../test/server";
import { ImportPage } from "./ImportPage";

/** GET /api/import answers `states` in order, then keeps answering the last one. */
function importStates(...states: ImportState[]): { gets: () => number } {
  let count = 0;
  server.use(
    http.get("/api/import", () => {
      const state = states[Math.min(count, states.length - 1)];
      count += 1;
      return HttpResponse.json(state);
    }),
  );
  return { gets: () => count };
}

function startAnswers(state: ImportState) {
  server.use(http.post("/api/import", () => HttpResponse.json(state, { status: 202 })));
}

async function nextPoll() {
  await act(() => vi.advanceTimersByTimeAsync(1000));
}

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
});

afterEach(() => {
  vi.useRealTimers();
});

function setupUser() {
  return userEvent.setup({ advanceTimers: (ms) => vi.advanceTimersByTime(ms) });
}

it("AC31: the page is in Finnish", async () => {
  importStates(IDLE);
  render(<ImportPage />);

  expect(screen.getByRole("heading", { name: "Tuonti" })).toBeInTheDocument();
  expect(
    screen.getByText("Kopioi kuittikuvat tuontikansioon ja paina Tuo kuitit."),
  ).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Tuo kuitit" })).toBeInTheDocument();
  expect(await screen.findByText("Tuontia ei ole vielä ajettu.")).toBeInTheDocument();
});

it("AC27: start an import, follow its progress and see the report", async () => {
  importStates(IDLE, FINISHED);
  startAnswers(running(1, 4));
  const user = setupUser();
  render(<ImportPage />);
  await screen.findByText("Tuontia ei ole vielä ajettu.");

  await user.click(screen.getByRole("button", { name: "Tuo kuitit" }));

  expect(await screen.findByText("Tuonti käynnissä: 1/4")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Tuo kuitit" })).toBeDisabled();

  await nextPoll();

  const report = await screen.findByRole("region", { name: "Edellinen tuonti" });
  expect(within(report).getByText("Tuotu: 1")).toBeInTheDocument();
  expect(within(report).getByText("Kaksoiskappaleita: 1")).toBeInTheDocument();
  expect(within(report).getByText("Epäonnistui: 1")).toBeInTheDocument();
  const duplicates = within(report).getByRole("list", {
    name: "Jo tuodut kuvat (jätetty tuontikansioon)",
  });
  expect(within(duplicates).getByText("b.jpg")).toBeInTheDocument();
  const failures = within(report).getByRole("list", {
    name: "Epäonnistuneet (siirretty epäonnistuneiden kansioon)",
  });
  const item = within(failures).getByRole("listitem");
  expect(item).toHaveTextContent("notes.txt");
  expect(item).toHaveTextContent("Tiedostomuotoa ei tueta. Käytä JPEG- tai PNG-kuvaa.");
  expect(screen.queryByText(/Tuonti käynnissä/)).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Tuo kuitit" })).toBeEnabled();
});

it("AC28: a running import is shown on page open and polled about every second", async () => {
  const answers = importStates(running(2, 5), FINISHED);
  render(<ImportPage />);

  expect(await screen.findByText("Tuonti käynnissä: 2/5")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Tuo kuitit" })).toBeDisabled();
  expect(answers.gets()).toBe(1);

  await nextPoll();

  expect(answers.gets()).toBe(2);
  expect(await screen.findByText("Tuotu: 1")).toBeInTheDocument();
  await nextPoll();
  expect(answers.gets()).toBe(2);
});

it.each([
  [
    "409",
    () =>
      HttpResponse.json(
        { error: "import_running", message: "Tuonti on jo käynnissä." },
        { status: 409 },
      ),
    "Tuonti on jo käynnissä.",
  ],
  [
    "503",
    () =>
      HttpResponse.json(
        {
          error: "folders_unavailable",
          message: "Kuvakansioita ei löydy tai niihin ei voi kirjoittaa.",
        },
        { status: 503 },
      ),
    "Kuvakansioita ei löydy tai niihin ei voi kirjoittaa.",
  ],
  ["network error", () => HttpResponse.error(), "Taustapalveluun ei saada yhteyttä."],
])("AC29: a refused start (%s) is shown and the report stays", async (_, answer, message) => {
  importStates(FINISHED);
  server.use(http.post("/api/import", answer));
  const user = setupUser();
  render(<ImportPage />);
  await screen.findByText("Tuotu: 1");

  await user.click(screen.getByRole("button", { name: "Tuo kuitit" }));

  expect(await screen.findByRole("alert")).toHaveTextContent(message);
  expect(screen.getByText("Tuotu: 1")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Tuo kuitit" })).toBeEnabled();
});

it("AC30: a run with nothing to import says so without counts", async () => {
  importStates({ ...IDLE, state: "finished", finished_at: "2026-10-28T10:00:00Z" });
  render(<ImportPage />);

  expect(await screen.findByText("Tuontikansiossa ei ollut kuvia.")).toBeInTheDocument();
  expect(screen.queryByText(/Tuotu:/)).not.toBeInTheDocument();
});

it("AC28: polling continues after a failed answer", async () => {
  let count = 0;
  server.use(
    http.get("/api/import", () => {
      count += 1;
      if (count === 2) {
        return HttpResponse.error();
      }
      return HttpResponse.json(count === 1 ? running(1, 3) : FINISHED);
    }),
  );
  render(<ImportPage />);
  await screen.findByText("Tuonti käynnissä: 1/3");

  await nextPoll();
  expect(await screen.findByRole("alert")).toHaveTextContent("Taustapalveluun ei saada yhteyttä.");

  await nextPoll();
  expect(await screen.findByText("Tuotu: 1")).toBeInTheDocument();
});

it("AC28: no request after the page is closed", async () => {
  const answers = importStates(running(1, 3));
  const { unmount } = render(<ImportPage />);
  await screen.findByText("Tuonti käynnissä: 1/3");

  unmount();
  await act(() => vi.advanceTimersByTimeAsync(3000));

  expect(answers.gets()).toBe(1);
});

it("AC27: a late answer to the first request does not hide a started run", async () => {
  let answerFirstGet = () => {};
  const firstGetAnswered = new Promise<void>((resolve) => {
    answerFirstGet = resolve;
  });
  server.use(
    http.get("/api/import", async () => {
      await firstGetAnswered;
      return HttpResponse.json(IDLE);
    }),
  );
  startAnswers(running(0, 2));
  const user = setupUser();
  render(<ImportPage />);

  await user.click(screen.getByRole("button", { name: "Tuo kuitit" }));
  expect(await screen.findByText("Tuonti käynnissä: 0/2")).toBeInTheDocument();
  answerFirstGet();
  await act(() => vi.advanceTimersByTimeAsync(0));

  expect(screen.getByText("Tuonti käynnissä: 0/2")).toBeInTheDocument();
  expect(screen.queryByText("Tuontia ei ole vielä ajettu.")).not.toBeInTheDocument();
});
