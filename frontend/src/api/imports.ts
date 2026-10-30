import { apiGet, apiPost, type ApiResult } from "./client";

export type FailureReason =
  | "unsupported_format"
  | "read_failed"
  | "unreadable_image"
  | "ocr_failed"
  | "no_text"
  | "parse_failed"
  | "save_failed"
  | "move_failed"
  | "internal_error";

/** Mirrors the backend schema of a failed file. */
export interface ImportFailure {
  file_name: string;
  reason: FailureReason;
  message: string;
}

/** Why a run stopped before its last file; the files left wait in the import folder. */
export interface ImportStopped {
  reason: "model_unavailable";
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
  stopped: ImportStopped | null;
}

export function getImport(): Promise<ApiResult<ImportState>> {
  return apiGet<ImportState>("/api/import");
}

export function startImport(): Promise<ApiResult<ImportState>> {
  return apiPost<ImportState>("/api/import", undefined);
}
