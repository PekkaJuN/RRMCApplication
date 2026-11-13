import { useEffect, useState, type MouseEvent } from "react";

// A few pages do not justify a router library; a router can replace this without changing the pages.
export type Page =
  | "products"
  | "import"
  | "receipts"
  | "receipt"
  | "totals"
  | "budget"
  | "comparison"
  | "archive"
  | "archiveYear";

/** Pages whose path holds an id: a receipt (`receiptPath`) and an archived year. */
type PageWithId = "receipt" | "archiveYear";

/** Pages with a fixed path. */
export const PAGE_PATHS: Record<Exclude<Page, PageWithId>, string> = {
  products: "/",
  import: "/tuonti",
  receipts: "/kuitit",
  totals: "/yhteenveto",
  budget: "/budjetti",
  comparison: "/vertailu",
  archive: "/arkisto",
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

const ARCHIVE_YEAR_PATH = /^\/arkisto\/([0-9]{4})$/;

/** The year in `/arkisto/<year>` (archiving spec PC15), or null for any other path. */
export function archiveYearFromPath(pathname: string): number | null {
  const match = ARCHIVE_YEAR_PATH.exec(pathname);
  return match ? Number(match[1]) : null;
}

export function pageFromPath(pathname: string): Page {
  if (receiptIdFromPath(pathname) !== null) {
    return "receipt";
  }
  if (archiveYearFromPath(pathname) !== null) {
    return "archiveYear";
  }
  if (pathname === PAGE_PATHS.archive || pathname.startsWith(`${PAGE_PATHS.archive}/`)) {
    return "archive";
  }
  if (pathname === PAGE_PATHS.receipts || pathname.startsWith(`${PAGE_PATHS.receipts}/`)) {
    return "receipts";
  }
  if (pathname === PAGE_PATHS.totals) {
    return "totals";
  }
  if (pathname === PAGE_PATHS.budget) {
    return "budget";
  }
  if (pathname === PAGE_PATHS.comparison) {
    return "comparison";
  }
  return pathname === PAGE_PATHS.import ? "import" : "products";
}

/**
 * The current page from the address, a function that opens another page (with the receipt
 * id or the archived year of a page that has one), the id of the open receipt and the open
 * archived year (null on other pages).
 */
export function usePage(): [Page, (page: Page, id?: number) => void, number | null, number | null] {
  const [path, setPath] = useState(() => window.location.pathname);

  useEffect(() => {
    const onPopState = () => setPath(window.location.pathname);
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  function go(next: Page, id?: number) {
    const nextPath = id !== undefined ? pathWithId(next, id) : pathOf(next);
    window.history.pushState(null, "", nextPath);
    setPath(nextPath);
  }

  return [pageFromPath(path), go, receiptIdFromPath(path), archiveYearFromPath(path)];
}

function pathWithId(page: Page, id: number): string {
  if (page === "receipt") {
    return receiptPath(id);
  }
  return page === "archiveYear" ? `${PAGE_PATHS.archive}/${id}` : pathOf(page);
}

function pathOf(page: Page): string {
  if (page === "receipt") {
    return PAGE_PATHS.receipts;
  }
  return page === "archiveYear" ? PAGE_PATHS.archive : PAGE_PATHS[page];
}

/** A click the page handles itself; one that opens a new tab or window is left to the browser. */
export function isPlainLeftClick(event: MouseEvent<HTMLAnchorElement>): boolean {
  return event.button === 0 && !event.ctrlKey && !event.metaKey && !event.shiftKey;
}
