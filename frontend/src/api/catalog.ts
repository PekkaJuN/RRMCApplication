import { apiDelete, apiGet, apiPatch, apiPost, type ApiResult } from "./client";

export type Kind = "group" | "category";

/** Mirrors the backend schema of a group or category. Only the count of its kind is set. */
export interface CatalogItem {
  id: number;
  name: string;
  kind: Kind;
  parent_id: number | null;
  product_count: number | null;
  category_count: number | null;
}

/** Mirrors the backend schema of a product. */
export interface Product {
  id: number;
  name: string;
  category_id: number;
  category_name: string;
  group_name: string | null;
}

export interface CategoryChanges {
  name?: string;
  kind?: Kind;
  /** `null` takes a category out of its group; leaving it out keeps the group. */
  parent_id?: number | null;
}

export interface ProductChanges {
  name?: string;
  category_id?: number;
}

export interface ProductFilter {
  q?: string;
  /** A category, or a group for the products of all its categories. */
  categoryId?: number;
}

export function listCategories(): Promise<ApiResult<CatalogItem[]>> {
  return apiGet<CatalogItem[]>("/api/categories");
}

export function createCategory(item: {
  name: string;
  kind: Kind;
  parent_id?: number | null;
}): Promise<ApiResult<CatalogItem>> {
  return apiPost<CatalogItem>("/api/categories", item);
}

export function updateCategory(
  id: number,
  changes: CategoryChanges,
): Promise<ApiResult<CatalogItem>> {
  return apiPatch<CatalogItem>(`/api/categories/${id}`, changes);
}

export function deleteCategory(id: number): Promise<ApiResult<undefined>> {
  return apiDelete(`/api/categories/${id}`);
}

export function listProducts(filter: ProductFilter): Promise<ApiResult<Product[]>> {
  const params = new URLSearchParams();
  if (filter.q) {
    params.set("q", filter.q);
  }
  if (filter.categoryId !== undefined) {
    params.set("category_id", String(filter.categoryId));
  }
  const query = params.toString();
  return apiGet<Product[]>(query ? `/api/products?${query}` : "/api/products");
}

export function createProduct(product: {
  name: string;
  category_id: number;
}): Promise<ApiResult<Product>> {
  return apiPost<Product>("/api/products", product);
}

export function updateProduct(id: number, changes: ProductChanges): Promise<ApiResult<Product>> {
  return apiPatch<Product>(`/api/products/${id}`, changes);
}

export function deleteProduct(id: number): Promise<ApiResult<undefined>> {
  return apiDelete(`/api/products/${id}`);
}
