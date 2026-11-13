import { act, renderHook } from "@testing-library/react";
import { beforeEach, expect, it } from "vitest";
import { archiveYearFromPath, pageFromPath, usePage } from "./navigation";

// Archiving spec PC14, PC15: the Arkisto page and one archived year.

beforeEach(() => {
  window.history.replaceState(null, "", "/");
});

it("archiving AC39: /arkisto is the archive and /arkisto/<year> one year", () => {
  expect(pageFromPath("/arkisto")).toBe("archive");
  expect(pageFromPath("/arkisto/2025")).toBe("archiveYear");
  expect(pageFromPath("/arkisto/2023")).toBe("archiveYear");
});

it("archiving AC41: a path that is not a year shows the archive page", () => {
  expect(pageFromPath("/arkisto/abc")).toBe("archive");
  expect(pageFromPath("/arkisto/20255")).toBe("archive");
  expect(pageFromPath("/arkisto/2025/x")).toBe("archive");
});

it("archiving AC39: the year comes from the path", () => {
  expect(archiveYearFromPath("/arkisto/2025")).toBe(2025);
  expect(archiveYearFromPath("/arkisto")).toBeNull();
  expect(archiveYearFromPath("/kuitit/2025")).toBeNull();
});

it("archiving AC39: go opens a year's path and gives its year", () => {
  const { result } = renderHook(() => usePage());

  act(() => result.current[1]("archiveYear", 2025));

  expect(window.location.pathname).toBe("/arkisto/2025");
  expect(result.current[0]).toBe("archiveYear");
  expect(result.current[3]).toBe(2025);
});

it("archiving PC14: go opens the archive page", () => {
  const { result } = renderHook(() => usePage());

  act(() => result.current[1]("archive"));

  expect(window.location.pathname).toBe("/arkisto");
});
