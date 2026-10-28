import type { MouseEvent } from "react";
import { ImportPage } from "./components/ImportPage";
import { ProductsPage } from "./components/ProductsPage";
import { StatusLine } from "./components/StatusLine";
import { fi } from "./i18n/fi";
import { PAGE_PATHS, usePage, type Page } from "./navigation";

const LINKS: { page: Page; text: string }[] = [
  { page: "products", text: fi.products.heading },
  { page: "import", text: fi.import.heading },
];

export function App() {
  const [page, go] = usePage();

  function open(event: MouseEvent<HTMLAnchorElement>, target: Page) {
    // Let the browser handle a click that opens a new tab or window.
    if (event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey) {
      return;
    }
    event.preventDefault();
    go(target);
  }

  return (
    <>
      <header>
        <h1>{fi.app.title}</h1>
        <nav aria-label={fi.app.navigation}>
          {LINKS.map((link) => (
            <a
              key={link.page}
              href={PAGE_PATHS[link.page]}
              aria-current={link.page === page ? "page" : undefined}
              onClick={(event) => open(event, link.page)}
            >
              {link.text}
            </a>
          ))}
        </nav>
        <StatusLine />
      </header>
      <main>{page === "import" ? <ImportPage /> : <ProductsPage />}</main>
    </>
  );
}
