import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  createProduct,
  deleteProduct,
  listCategories,
  listProducts,
  updateProduct,
  type CatalogItem,
  type Product,
} from "../api/catalog";
import type { ApiResult } from "../api/client";
import { fi } from "../i18n/fi";
import { CategoryPanel } from "./CategoryPanel";
import { CategorySelect } from "./CategorySelect";
import { CategoryTools } from "./CategoryTools";
import { ConfirmDelete } from "./ConfirmDelete";

type Run = (key: string, action: () => Promise<ApiResult<unknown>>) => Promise<boolean>;

/**
 * The Tuotteet page in two columns (products two columns PC1): the category tree, and the
 * products of the selected group or category with that item's tools.
 */
export function ProductsPage() {
  // null until the categories have loaded once.
  const [loadedItems, setItems] = useState<CatalogItem[] | null>(null);
  const [products, setProducts] = useState<Product[] | null>(null);
  const [query, setQuery] = useState("");
  // null is "Kaikki tuotteet".
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [categoriesError, setCategoriesError] = useState<string | null>(null);
  const [productsError, setProductsError] = useState<string | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  // Bumped after every successful write, so both lists and all counts come from the backend.
  const [version, setVersion] = useState(0);
  const reload = useCallback(() => setVersion((current) => current + 1), []);
  const items = loadedItems ?? [];
  // A selection whose item was deleted meanwhile falls back to all products (PC6, PC10).
  const selected = items.find((item) => item.id === selectedId) ?? null;
  const activeSelectedId = selected?.id ?? null;
  const groups = items.filter((item) => item.kind === "group");

  useEffect(() => {
    let isCurrent = true;
    void listCategories().then((result) => {
      if (!isCurrent) {
        return;
      }
      if (result.ok) {
        setItems(result.data);
        setCategoriesError(null);
      } else {
        setCategoriesError(result.error.message);
      }
    });
    return () => {
      isCurrent = false;
    };
  }, [version]);

  useEffect(() => {
    let isCurrent = true;
    void listProducts({ q: query, categoryId: activeSelectedId ?? undefined }).then((result) => {
      if (!isCurrent) {
        return;
      }
      if (result.ok) {
        setProducts(result.data);
        setProductsError(null);
      } else {
        setProductsError(result.error.message);
      }
    });
    return () => {
      isCurrent = false;
    };
  }, [query, activeSelectedId, version]);

  const run: Run = async (key, action) => {
    const result = await action();
    setErrors((current) => {
      const next = { ...current };
      if (result.ok) {
        delete next[key];
      } else {
        next[key] = result.error.message;
      }
      return next;
    });
    if (result.ok) {
      reload();
    }
    return result.ok;
  };

  const isFiltered = query !== "" || activeSelectedId !== null;
  const loadErrors = [...new Set([categoriesError, productsError])].filter((error) => error);

  return (
    <section className="products-page" aria-labelledby="products-heading">
      <h2 id="products-heading">{fi.products.heading}</h2>
      {loadErrors.map((error) => (
        <p key={error} role="alert">
          {error}
        </p>
      ))}
      <div className="products-columns">
        <CategoryPanel
          items={items}
          selectedId={activeSelectedId}
          onSelect={setSelectedId}
          onChanged={reload}
        />
        <section className="product-column" aria-labelledby="product-column-heading">
          <h3 id="product-column-heading">{selected?.name ?? fi.products.allProducts}</h3>
          {selected && (
            <CategoryTools key={selected.id} item={selected} groups={groups} onChanged={reload} />
          )}
          <div>
            <input
              type="search"
              aria-label={fi.products.search}
              placeholder={fi.products.search}
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </div>
          <AddProductForm
            items={items}
            isLoaded={loadedItems !== null}
            suggestedId={selected?.kind === "category" ? selected.id : null}
            error={errors.newProduct}
            run={run}
          />
          <ProductTable products={products} items={items} errors={errors} run={run} />
          {products?.length === 0 && (
            <p>{isFiltered ? fi.products.noMatches : fi.products.noProducts}</p>
          )}
        </section>
      </div>
    </section>
  );
}

interface ProductTableProps {
  products: Product[] | null;
  items: CatalogItem[];
  errors: Record<string, string>;
  run: Run;
}

function ProductTable({ products, items, errors, run }: ProductTableProps) {
  return (
    <div className="table-box">
      <table aria-label={fi.products.table}>
        <thead>
          <tr>
            <th scope="col">{fi.products.name}</th>
            <th scope="col">{fi.products.category}</th>
            <th scope="col" />
          </tr>
        </thead>
        <tbody>
          {products?.map((item) => (
            <ProductRow
              key={item.id}
              product={item}
              items={items}
              error={errors[`product-${item.id}`]}
              run={run}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}

interface AddProductFormProps {
  items: CatalogItem[];
  /** False until the categories have loaded, so "no categories" is not claimed early. */
  isLoaded: boolean;
  /** The selected category, which the dropdown starts at (PC8); null for none. */
  suggestedId: number | null;
  error: string | undefined;
  run: Run;
}

function AddProductForm({ items, isLoaded, suggestedId, error, run }: AddProductFormProps) {
  const [name, setName] = useState("");
  // The user's choice holds while the suggestion it was made under is current; a new
  // selection shows its own suggestion (P2). No effect sets state.
  const [chosen, setChosen] = useState<{ suggestedId: number | null; id: number | null }>({
    suggestedId,
    id: suggestedId,
  });
  const chosenId = chosen.suggestedId === suggestedId ? chosen.id : suggestedId;
  const [hint, setHint] = useState<string | null>(null);
  const hasCategories = items.some((item) => item.kind === "category");
  // A choice that was deleted or turned into a group meanwhile is no choice.
  const categoryId = items.some((item) => item.id === chosenId && item.kind === "category")
    ? chosenId
    : null;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!hasCategories || categoryId === null) {
      setHint(hasCategories ? fi.products.chooseCategory : fi.products.categoryNeeded);
      return;
    }
    setHint(null);
    if (await run("newProduct", () => createProduct({ name, category_id: categoryId }))) {
      setName("");
    }
  };

  return (
    <form aria-label={fi.products.newProduct} onSubmit={(event) => void submit(event)}>
      <h4>{fi.products.newProduct}</h4>
      <input
        aria-label={fi.products.newProductName}
        value={name}
        onChange={(event) => setName(event.target.value)}
      />{" "}
      <CategorySelect
        label={fi.products.category}
        items={items}
        value={categoryId}
        onChange={(id) => setChosen({ suggestedId, id })}
      />{" "}
      <button type="submit">{fi.actions.add}</button>
      {isLoaded && !hasCategories && <p>{fi.products.categoryNeeded}</p>}
      {hint && hasCategories && <p>{hint}</p>}
      {error && <p role="alert">{error}</p>}
    </form>
  );
}

interface ProductRowProps {
  product: Product;
  items: CatalogItem[];
  error: string | undefined;
  run: Run;
}

function ProductRow({ product, items, error, run }: ProductRowProps) {
  const [draft, setDraft] = useState<string | null>(null);
  const key = `product-${product.id}`;

  const save = async (event: FormEvent) => {
    event.preventDefault();
    if (draft !== null && (await run(key, () => updateProduct(product.id, { name: draft })))) {
      setDraft(null);
    }
  };

  return (
    <tr>
      <td>
        {draft === null ? (
          <span data-name>{product.name}</span>
        ) : (
          <form onSubmit={(event) => void save(event)}>
            <input
              aria-label={fi.products.newProductName}
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
            />
            <button type="submit">{fi.actions.save}</button>
            <button type="button" onClick={() => setDraft(null)}>
              {fi.actions.cancel}
            </button>
          </form>
        )}
        {error && <p role="alert">{error}</p>}
      </td>
      <td>
        <CategorySelect
          label={fi.products.category}
          items={items}
          value={product.category_id}
          onChange={(categoryId) => {
            if (categoryId !== null) {
              void run(key, () => updateProduct(product.id, { category_id: categoryId }));
            }
          }}
        />
      </td>
      <td>
        {draft === null && (
          <button type="button" onClick={() => setDraft(product.name)}>
            {fi.actions.rename}
          </button>
        )}{" "}
        <ConfirmDelete onConfirm={() => void run(key, () => deleteProduct(product.id))} />
      </td>
    </tr>
  );
}
