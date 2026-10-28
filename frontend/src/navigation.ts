import { useEffect, useState } from "react";

// Two pages do not justify a router library; a router can replace this without changing the pages.
export type Page = "products" | "import";

export const PAGE_PATHS: Record<Page, string> = { products: "/", import: "/tuonti" };

export function pageFromPath(pathname: string): Page {
  return pathname === PAGE_PATHS.import ? "import" : "products";
}

/** The current page from the address, and a function that opens another page. */
export function usePage(): [Page, (page: Page) => void] {
  const [page, setPage] = useState(() => pageFromPath(window.location.pathname));

  useEffect(() => {
    const onPopState = () => setPage(pageFromPath(window.location.pathname));
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  function go(next: Page) {
    window.history.pushState(null, "", PAGE_PATHS[next]);
    setPage(next);
  }

  return [page, go];
}
