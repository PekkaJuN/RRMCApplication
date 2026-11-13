import { apiDelete, apiGet, apiPost, type ApiResult } from "./client";

/** Mirrors the backend schemas of /api/archive (archiving spec P4). */
export interface ArchivedYear {
  year: number;
  receipts: number;
  lines: number;
  images: number;
}

export interface ArchiveCandidate extends ArchivedYear {
  unreviewed: number;
}

export interface ArchiveOverview {
  archived: ArchivedYear[];
  candidates: ArchiveCandidate[];
}

export interface ArchiveResult {
  year: number;
  receipts: number;
  lines: number;
  images_moved: number;
  images_not_moved: string[];
}

export interface DeletedYear {
  year: number;
  receipts: number;
  lines: number;
}

/** A group, a category, a product, or the lines without a category (`kind` `none`). */
export interface ArchiveRow {
  kind: "group" | "category" | "product" | "none";
  name: string | null;
  /** Cents per month, January first. */
  months: number[];
  total: number;
  children: ArchiveRow[];
}

export interface ArchiveTotals {
  year: number;
  months: string[];
  rows: ArchiveRow[];
  month_totals: number[];
  total: number;
}

export function getArchive(): Promise<ApiResult<ArchiveOverview>> {
  return apiGet<ArchiveOverview>("/api/archive");
}

export function archiveYear(year: number): Promise<ApiResult<ArchiveResult>> {
  return apiPost<ArchiveResult>(`/api/archive/${year}`, undefined);
}

export function deleteArchivedYear(year: number): Promise<ApiResult<DeletedYear>> {
  return apiDelete<DeletedYear>(`/api/archive/${year}`);
}

export function getArchiveTotals(year: number): Promise<ApiResult<ArchiveTotals>> {
  return apiGet<ArchiveTotals>(`/api/archive/${year}/totals`);
}

/** The download URL of an archived year's CSV file (archiving spec PC13). */
export function archiveCsvUrl(year: number): string {
  return `/api/export/archive/${year}`;
}
