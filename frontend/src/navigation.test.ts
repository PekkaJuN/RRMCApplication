import { act, renderHook } from "@testing-library/react";
import { beforeEach, expect, it } from "vitest";
import { pageFromPath, usePage } from "./navigation";

beforeEach(() => {
  window.history.replaceState(null, "", "/");
});

it("AC26: /tuonti is the Tuonti page and every other path is Tuotteet", () => {
  expect(pageFromPath("/tuonti")).toBe("import");
  expect(pageFromPath("/")).toBe("products");
  expect(pageFromPath("/muu")).toBe("products");
});

it("AC26: go pushes the page's path", () => {
  const { result } = renderHook(() => usePage());

  act(() => result.current[1]("import"));

  expect(result.current[0]).toBe("import");
  expect(window.location.pathname).toBe("/tuonti");
});

it("AC26: the back button switches the page back", () => {
  const { result } = renderHook(() => usePage());
  act(() => result.current[1]("import"));

  act(() => {
    window.history.replaceState(null, "", "/");
    window.dispatchEvent(new PopStateEvent("popstate"));
  });

  expect(result.current[0]).toBe("products");
});
