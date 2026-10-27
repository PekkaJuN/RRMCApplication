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
import { ConfirmDelete } from "./ConfirmDelete";

type Run = (key: string, action: () => Promise<ApiResult<unknown>>) => Promise<boolean>;

/** The Tuotteet page: the category panel and the product table (PC9). */
export function ProductsPage() {
  // null until the categories have loaded once.
  const [loadedItems, setItems] = useState<CatalogItem[] | null>(null);
  const [products, setProducts] = useState<Product[] | null>(null);
  const [query, setQuery] = useState("");
  const [filterId, setFilterId] = useState<number | null>(null);
  const [categoriesError, setCategoriesError] = useState<string | null>(null);
  const [productsError, setProductsError] = useState<string | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  // Bumped after every successful write, so both lists and all counts come from the backend.
  const [version, setVersion] = useState(0);
  const reload = useCallback(() => setVersion((current) => current + 1), []);
  const items = loadedItems ?? [];
  // A filter on an item that was deleted meanwhile falls back to all products.
  const activeFilterId = items.some((item) => item.id === filterId) ? filterId : null;

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
    void listProducts({ q: query, categoryId: activeFilterId ?? undefined }).then((result) => {
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
  }, [query, activeFilterId, version]);

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

  const isFiltered = query !== "" || activeFilterId !== null;
  const loadErrors = [...new Set([categoriesError, productsError])].filter((error) => error);

  return (
    <section aria-labelledby="products-heading">
      <h2 id="products-heading">{fi.products.heading}</h2>
      {loadErrors.map((error) => (
        <p key={error} role="alert">
          {error}
        </p>
      ))}
      <CategoryPanel items={items} onChanged={reload} />
      <div>
        <input
          type="search"
          aria-label={fi.products.search}
          placeholder={fi.products.search}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />{" "}
        <CategorySelect
          label={fi.products.filter}
          items={items}
          value={activeFilterId}
          onChange={setFilterId}
          isFilter
        />
      </div>
      <AddProductForm
        items={items}
        isLoaded={loadedItems !== null}
        error={errors.newProduct}
        run={run}
      />
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
      {products?.length === 0 && (
        <p>{isFiltered ? fi.products.noMatches : fi.products.noProducts}</p>
      )}
    </section>
  );
}

interface AddProductFormProps {
  items: CatalogItem[];
  /** False until the categories have loaded, so "no categories" is not claimed early. */
  isLoaded: boolean;
  error: string | undefined;
  run: Run;
}

function AddProductForm({ items, isLoaded, error, run }: AddProductFormProps) {
  const [name, setName] = useState("");
  const [chosenId, setChosenId] = useState<number | null>(null);
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
      <h3>{fi.products.newProduct}</h3>
      <input
        aria-label={fi.products.newProductName}
        value={name}
        onChange={(event) => setName(event.target.value)}
      />{" "}
      <CategorySelect
        label={fi.products.category}
        items={items}
        value={categoryId}
        onChange={setChosenId}
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
