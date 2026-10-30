import type { MouseEvent } from "react";
import { ImportPage } from "./components/ImportPage";
import { ProductsPage } from "./components/ProductsPage";
import { ReceiptPage } from "./components/ReceiptPage";
import { ReceiptsPage } from "./components/ReceiptsPage";
import { StatusLine } from "./components/StatusLine";
import { fi } from "./i18n/fi";
import { isPlainLeftClick, PAGE_PATHS, usePage, type Page } from "./navigation";

const LINKS: { page: Exclude<Page, "receipt">; text: string }[] = [
  { page: "products", text: fi.products.heading },
  { page: "import", text: fi.import.heading },
  { page: "receipts", text: fi.receipts.heading },
];

export function App() {
  const [page, go, receiptId] = usePage();
  // A receipt belongs to the Kuitit section of the navigation.
  const section = page === "receipt" ? "receipts" : page;

  function open(event: MouseEvent<HTMLAnchorElement>, target: Page) {
    if (!isPlainLeftClick(event)) {
      return;
    }
    event.preventDefault();
    go(target);
  }

  function content() {
    switch (page) {
      case "import":
        return <ImportPage />;
      case "receipts":
        return <ReceiptsPage onOpen={(id) => go("receipt", id)} />;
      case "receipt":
        // `receiptId` is set whenever the page is `receipt`; the key reloads on another id.
        return <ReceiptPage key={receiptId} id={receiptId ?? 0} onBack={() => go("receipts")} />;
      default:
        return <ProductsPage />;
    }
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
              aria-current={link.page === section ? "page" : undefined}
              onClick={(event) => open(event, link.page)}
            >
              {link.text}
            </a>
          ))}
        </nav>
        <StatusLine />
      </header>
      <main>{content()}</main>
    </>
  );
}
