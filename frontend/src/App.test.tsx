import { render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { beforeEach, expect, it } from "vitest";
import indexHtml from "../index.html?raw";
import type { Health } from "./api/health";
import { App } from "./App";
import { server } from "./test/server";

const HEALTHY: Health = {
  status: "ok",
  model_name: "qwen2.5:7b",
  checks: { database: "ok", folders: "ok", ocr: "ok", model: "ok" },
};

beforeEach(() => {
  server.use(http.get("/api/health", () => HttpResponse.json(HEALTHY)));
});

it("AC25: shows the heading, the navigation and the status line", async () => {
  render(<App />);

  expect(screen.getByRole("heading", { level: 1, name: "Kuittisovellus" })).toBeInTheDocument();
  expect(screen.getByRole("navigation", { name: "Päävalikko" })).toBeInTheDocument();
  expect(await screen.findByText("Kaikki palvelut toiminnassa")).toBeInTheDocument();
});

it("AC25: shows no English text", async () => {
  const { container } = render(<App />);
  await screen.findByText("Kaikki palvelut toiminnassa");

  // Every visible text and accessible name is one of the Finnish texts of the shell.
  expect(container.textContent).toBe("KuittisovellusKaikki palvelut toiminnassa");
  const labels = [...container.querySelectorAll("[aria-label]")].map((element) =>
    element.getAttribute("aria-label"),
  );
  expect(labels.sort()).toEqual(["Palveluiden tila", "Päävalikko"]);
});

it("AC25: the page is Finnish and the tab title is Kuittisovellus", () => {
  const page = new DOMParser().parseFromString(indexHtml, "text/html");

  expect(page.documentElement.lang).toBe("fi");
  expect(page.title).toBe("Kuittisovellus");
});
