import { useEffect, useState, type MouseEvent } from "react";

// A few pages do not justify a router library; a router can replace this without changing the pages.
export type Page = "products" | "import" | "receipts" | "receipt";

/** Pages with a fixed path; a receipt's path holds its id (`receiptPath`). */
export const PAGE_PATHS: Record<Exclude<Page, "receipt">, string> = {
  products: "/",
  import: "/tuonti",
  receipts: "/kuitit",
};

const RECEIPT_PATH = /^\/kuitit\/([1-9][0-9]*)$/;

export function receiptPath(id: number): string {
  return `${PAGE_PATHS.receipts}/${id}`;
}

/** The id in `/kuitit/<id>`, or null for any other path. */
export function receiptIdFromPath(pathname: string): number | null {
  const match = RECEIPT_PATH.exec(pathname);
  return match ? Number(match[1]) : null;
}

export function pageFromPath(pathname: string): Page {
  if (receiptIdFromPath(pathname) !== null) {
    return "receipt";
  }
  if (pathname === PAGE_PATHS.receipts || pathname.startsWith(`${PAGE_PATHS.receipts}/`)) {
    return "receipts";
  }
  return pathname === PAGE_PATHS.import ? "import" : "products";
}

/**
 * The current page from the address, a function that opens another page, and the id of the
 * open receipt (null on other pages).
 */
export function usePage(): [Page, (page: Page, receiptId?: number) => void, number | null] {
  const [path, setPath] = useState(() => window.location.pathname);

  useEffect(() => {
    const onPopState = () => setPath(window.location.pathname);
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  function go(next: Page, receiptId?: number) {
    const nextPath =
      next === "receipt" && receiptId !== undefined ? receiptPath(receiptId) : pathOf(next);
    window.history.pushState(null, "", nextPath);
    setPath(nextPath);
  }

  return [pageFromPath(path), go, receiptIdFromPath(path)];
}

function pathOf(page: Page): string {
  return page === "receipt" ? PAGE_PATHS.receipts : PAGE_PATHS[page];
}

/** A click the page handles itself; one that opens a new tab or window is left to the browser. */
export function isPlainLeftClick(event: MouseEvent<HTMLAnchorElement>): boolean {
  return event.button === 0 && !event.ctrlKey && !event.metaKey && !event.shiftKey;
}
