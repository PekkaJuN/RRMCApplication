import { act, renderHook } from "@testing-library/react";
import { beforeEach, expect, it } from "vitest";
import { pageFromPath, receiptIdFromPath, receiptPath, usePage } from "./navigation";

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

// Receipt review spec: the Kuitit page and one receipt.

it("AC20, AC22: /kuitit is the list and /kuitit/<id> one receipt", () => {
  expect(pageFromPath("/kuitit")).toBe("receipts");
  expect(pageFromPath("/kuitit/7")).toBe("receipt");
  expect(pageFromPath("/kuitit/07")).toBe("receipts");
  expect(pageFromPath("/kuitit/x")).toBe("receipts");
  expect(pageFromPath("/kuitit/7/x")).toBe("receipts");
  expect(pageFromPath("/")).toBe("products");
});

it("AC22: the receipt id comes from the path", () => {
  expect(receiptIdFromPath("/kuitit/7")).toBe(7);
  expect(receiptIdFromPath("/kuitit/123")).toBe(123);
  expect(receiptIdFromPath("/kuitit/0")).toBeNull();
  expect(receiptIdFromPath("/kuitit")).toBeNull();
  expect(receiptIdFromPath("/tuonti")).toBeNull();
  expect(receiptPath(7)).toBe("/kuitit/7");
});

it("AC22: go opens a receipt by its id", () => {
  const { result } = renderHook(() => usePage());

  act(() => result.current[1]("receipt", 7));

  expect(result.current[0]).toBe("receipt");
  expect(result.current[2]).toBe(7);
  expect(window.location.pathname).toBe("/kuitit/7");
});

it("AC22: the back button returns from a receipt to the list", () => {
  const { result } = renderHook(() => usePage());
  act(() => result.current[1]("receipts"));
  act(() => result.current[1]("receipt", 7));

  act(() => {
    window.history.replaceState(null, "", "/kuitit");
    window.dispatchEvent(new PopStateEvent("popstate"));
  });

  expect(result.current[0]).toBe("receipts");
  expect(result.current[2]).toBeNull();
});
