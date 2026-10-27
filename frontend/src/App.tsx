import { ProductsPage } from "./components/ProductsPage";
import { StatusLine } from "./components/StatusLine";
import { fi } from "./i18n/fi";

export function App() {
  return (
    <>
      <header>
        <h1>{fi.app.title}</h1>
        {/* One page so far, so no router yet; the first spec with a second page adds one. */}
        <nav aria-label={fi.app.navigation}>
          <a href="/" aria-current="page">
            {fi.products.heading}
          </a>
        </nav>
        <StatusLine />
      </header>
      <main>
        <ProductsPage />
      </main>
    </>
  );
}
