import { apiGet, apiPost, type ApiResult } from "./client";

export type FailureReason =
  "unsupported_format" | "read_failed" | "save_failed" | "move_failed" | "internal_error";

/** Mirrors the backend schema of a failed file. */
export interface ImportFailure {
  file_name: string;
  reason: FailureReason;
  message: string;
}

/** Mirrors the backend schema of GET /api/import: the current or latest run. */
export interface ImportState {
  state: "idle" | "running" | "finished";
  total: number;
  processed: number;
  imported: number;
  duplicates: string[];
  failures: ImportFailure[];
  started_at: string | null;
  finished_at: string | null;
}

export function getImport(): Promise<ApiResult<ImportState>> {
  return apiGet<ImportState>("/api/import");
}

export function startImport(): Promise<ApiResult<ImportState>> {
  return apiPost<ImportState>("/api/import", undefined);
}
